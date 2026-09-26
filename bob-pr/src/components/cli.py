"""Command-line interface: the verbs the agent calls between review steps.

Commands: new, snapshot, diff, serve, stop, decision, revise, apply,
close, comment, list.
All state lives in .bob-pr/bob_pr.db under the current project root.
serve runs the review server as a detached background process so the
agent's shell returns immediately; stop kills it.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time

from components.database import init_db
from components.decisions import get_decision, post_comment
from components.pull_requests import close_pr, create_pr, list_prs, revise
from components.server import DEFAULT_PORT, make_server
from components.snapshots import (
    apply_pr,
    cleanup_shadows,
    compute_diffs,
    snapshot_pr,
)

DB_DIR = ".bob-pr"
DB_NAME = "bob_pr.db"


def _database_path(args):
    """Resolve the database path: --db flag, env var, or .bob-pr/ under cwd."""
    return args.db or os.environ.get(
        "BOB_PR_DB", os.path.join(os.getcwd(), DB_DIR, DB_NAME)
    )


def _split_file_paths(value):
    """Split a comma-separated --files argument into a clean path list."""
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _load_diffs_file(value):
    """Load a {path: diff_text} mapping from a JSON file for --diffs."""
    if not value:
        return None
    with open(value) as handle:
        return json.load(handle)


SERVE_STATE_FILES = ("serve.pid", "serve.port")
SERVE_LOG_NAME = "serve.log"


def _bob_pr_script():
    """Return the absolute path of the bob_pr.py facade next to src/."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "bob_pr.py",
    )


def _remove_state_files(state_dir):
    """Delete the serve.pid and serve.port markers, ignoring absence."""
    for name in SERVE_STATE_FILES:
        try:
            os.remove(os.path.join(state_dir, name))
        except OSError:
            pass


def _other_server_pids():
    """Yield pids of running `bob_pr.py serve` processes, except self.

    Reads /proc/<pid>/cmdline as real argv, not a text match — a shell
    quoting the string (bash -c '...bob_pr.py serve...') never matches.
    The parent pid is excluded too: the detached child's own spawner runs
    `bob_pr.py serve` and must not take the SIGTERM. Silently yields
    nothing on systems without /proc.
    """
    protected = {os.getpid(), os.getppid()}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return
    for name in entries:
        if not name.isdigit() or int(name) in protected:
            continue
        try:
            with open(f"/proc/{name}/cmdline", "rb") as handle:
                argv = handle.read().split(b"\0")
        except OSError:
            continue
        is_script = any(
            arg == b"bob_pr.py" or arg.endswith(b"/bob_pr.py")
            for arg in argv
        )
        if is_script and b"serve" in argv:
            yield int(name)


def _wait_for_death(pids, timeout=2.0):
    """Block until each pid exits or zombies. Best-effort, bounded.

    Reads /proc/<pid>/stat for the state field — 'Z' counts as dead.
    """
    deadline = time.time() + timeout
    for pid in pids:
        while time.time() < deadline:
            try:
                with open(f"/proc/{pid}/stat", "rb") as handle:
                    state = handle.read().rsplit(b")", 1)[1].split()[0]
                if state == b"Z":
                    break
            except OSError:
                break
            time.sleep(0.05)


def _kill_other_servers():
    """SIGTERM every running bob-pr server except this process.

    Uses _other_server_pids, so orphan servers with no pid file are
    caught too. Waits for the kills to land so a follow-up pid check
    never sees a dying server as alive. Silent when no server runs.
    """
    pids = list(_other_server_pids())
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    _wait_for_death(pids)


def _pid_is_bob_pr(pid):
    """True when the pid's command line mentions bob_pr.py (/proc check).

    Unreadable processes are trusted — the pid file is ours to honor.
    """
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            return b"bob_pr.py" in handle.read()
    except OSError:
        return True


def _serve_foreground(args, project_root, database_path):
    """Run the review server in the foreground (the child process mode).

    Writes serve.port and serve.pid next to the database so the parent
    process and the stop command can find the running instance, then
    blocks until interrupted or killed.
    """
    state_dir = os.path.dirname(database_path) or "."
    try:
        server = make_server(database_path, args.port, project_root)
    except OSError:
        print(
            f"error: port {args.port} is in use — bob-pr refuses to "
            "serve on another port",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(os.path.join(state_dir, "serve.pid"), "w") as handle:
        handle.write(str(os.getpid()))
    with open(os.path.join(state_dir, "serve.port"), "w") as handle:
        handle.write(str(server.server_address[1]))
    print(f"Serving on http://localhost:{server.server_address[1]}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        _remove_state_files(state_dir)


def _running_server(state_dir):
    """Return (pid, port) of a live background server, else None.

    Reads serve.pid and serve.port; a dead pid means stale files from a
    crashed run — they get cleaned and None is returned.
    """
    try:
        with open(os.path.join(state_dir, "serve.pid")) as handle:
            pid = int(handle.read().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        _remove_state_files(state_dir)
        return None
    if not _pid_is_bob_pr(pid):
        _remove_state_files(state_dir)
        return None
    try:
        with open(os.path.join(state_dir, "serve.port")) as handle:
            port = int(handle.read().strip())
    except (OSError, ValueError):
        port = None
    return pid, port


def _spawn_server(args, project_root, database_path):
    """Spawn the review server as a detached child and return at once.

    The child runs `serve --foreground`; it writes serve.port next to the
    database when its socket is bound. The parent polls that file for up
    to 5 seconds, then prints the URL so the caller knows where to point
    the reviewer. Child output goes to serve.log in the same directory.
    A live server for the same database is reported, never duplicated.
    """
    state_dir = os.path.dirname(database_path) or "."
    running = _running_server(state_dir)
    if running:
        pid, port = running
        url = f"http://localhost:{port}/" if port else "(port unknown)"
        print(f"Already serving on {url} (pid {pid})")
        return
    os.makedirs(state_dir, exist_ok=True)
    script = _bob_pr_script()
    log_path = os.path.join(state_dir, SERVE_LOG_NAME)
    port_path = os.path.join(state_dir, "serve.port")
    try:
        os.remove(port_path)
    except OSError:
        pass
    log_handle = open(log_path, "ab")
    process = subprocess.Popen(
        [
            sys.executable,
            script,
            "--db",
            database_path,
            "serve",
            "--foreground",
            "--port",
            str(args.port),
        ],
        cwd=project_root,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    port = None
    for _ in range(50):
        if process.poll() is not None:
            break
        try:
            with open(port_path) as handle:
                port = int(handle.read().strip())
            break
        except (OSError, ValueError):
            time.sleep(0.1)
    if port is not None:
        print(f"Serving on http://localhost:{port}/ (pid {process.pid})")
    else:
        print(f"Server failed to start (pid {process.pid})")
        try:
            with open(log_path, "rb") as handle:
                tail = handle.read().decode(errors="replace").splitlines()[-5:]
            for line in tail:
                print(f"  {line}")
        except OSError:
            pass
    print(f"Log: {log_path}")
    print(f"Stop: python3 {script} --db {database_path} stop")


def _stop_server(database_path):
    """Stop the background review server recorded in serve.pid.

    Sends SIGTERM to the recorded pid and removes the state files. A
    missing pid file or a dead process prints a clean message instead
    of raising.
    """
    state_dir = os.path.dirname(database_path) or "."
    pid_path = os.path.join(state_dir, "serve.pid")
    try:
        with open(pid_path) as handle:
            pid = int(handle.read().strip())
    except (OSError, ValueError):
        print("no background server recorded")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped server (pid {pid})")
    except OSError:
        print(f"server pid {pid} not running")
    _remove_state_files(state_dir)


def _build_parser():
    """Build the argparse parser with all bob-pr subcommands."""
    parser = argparse.ArgumentParser(
        prog="bob_pr",
        description="Present an agent plan as a GitHub-style pull request page.",
    )
    parser.add_argument("--db", help="database path (default: .bob-pr/bob_pr.db)")
    subcommands = parser.add_subparsers(dest="command", required=True)

    new_cmd = subcommands.add_parser("new", help="create a PR from a plan")
    new_cmd.add_argument("--title", required=True)
    new_cmd.add_argument("--summary", required=True)
    new_cmd.add_argument("--files", default="")
    new_cmd.add_argument("--diffs", help="JSON file of hand-written diffs")

    snapshot_cmd = subcommands.add_parser(
        "snapshot", help="copy planned files into .bob-pr/tmp/<id>/"
    )
    snapshot_cmd.add_argument("id", type=int)

    diff_cmd = subcommands.add_parser(
        "diff", help="compute diffs of shadow copies vs originals"
    )
    diff_cmd.add_argument("id", type=int)

    serve_cmd = subcommands.add_parser(
        "serve", help="start the review server in the background"
    )
    serve_cmd.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve_cmd.add_argument(
        "--foreground",
        action="store_true",
        help="run in the foreground (used by the background child)",
    )

    subcommands.add_parser(
        "stop", help="stop the background review server"
    )

    decision_cmd = subcommands.add_parser(
        "decision", help="print the verdict for a PR"
    )
    decision_cmd.add_argument("id", type=int)

    revise_cmd = subcommands.add_parser(
        "revise", help="add a new revision to a PR"
    )
    revise_cmd.add_argument("id", type=int)
    revise_cmd.add_argument("--summary", required=True)
    revise_cmd.add_argument("--files", default="")
    revise_cmd.add_argument("--diffs", help="JSON file of hand-written diffs")

    apply_cmd = subcommands.add_parser(
        "apply", help="install shadow copies over the real files"
    )
    apply_cmd.add_argument("id", type=int)

    close_cmd = subcommands.add_parser(
        "close", help="close a rejected or abandoned plan"
    )
    close_cmd.add_argument("id", type=int)

    comment_cmd = subcommands.add_parser(
        "comment", help="post a note on the PR timeline"
    )
    comment_cmd.add_argument("id", type=int)
    comment_cmd.add_argument("--body", required=True)

    subcommands.add_parser("list", help="list all PRs")
    return parser


def main(argv=None):
    """Parse CLI arguments and run the requested subcommand."""
    args = _build_parser().parse_args(argv)
    connection = init_db(_database_path(args))
    project_root = os.getcwd()

    if args.command == "new":
        pull_request_id = create_pr(
            connection,
            args.title,
            args.summary,
            _split_file_paths(args.files),
            diffs=_load_diffs_file(args.diffs),
        )
        print(f"PR_ID={pull_request_id}")
        print(f"Created PLAN-PR #{pull_request_id}: {args.title}")
    elif args.command == "snapshot":
        manifest = snapshot_pr(connection, args.id, project_root)
        copied = sum(1 for v in manifest.values() if v["sha256"])
        print(f"Snapshotted {copied} file(s) into .bob-pr/tmp/{args.id}/")
        print(f"New files (no original): "
              f"{[k for k, v in manifest.items() if v['sha256'] is None]}")
        kept = [k for k, v in manifest.items() if v.get("kept_edits")]
        if kept:
            print(f"Kept edited copies (not overwritten): {kept}")
    elif args.command == "diff":
        from components.pull_requests import latest_revision
        revision = latest_revision(connection, args.id)
        if revision and not json.loads(revision[3]):
            print(
                f"Warning: PR #{args.id} revision {revision[1]} has no "
                f"planned files. Re-run revise with --files."
            )
        diffs = compute_diffs(connection, args.id, project_root)
        changed = [p for p, d in diffs.items() if d]
        print(f"Diffs stored for {len(changed)} changed file(s): {changed}")
    elif args.command == "serve":
        database_path = _database_path(args)
        _kill_other_servers()
        if args.foreground:
            _serve_foreground(args, project_root, database_path)
        else:
            _spawn_server(args, project_root, database_path)
    elif args.command == "stop":
        _stop_server(_database_path(args))
    elif args.command == "decision":
        verdict, comments = get_decision(connection, args.id)
        print(f"STATUS: {verdict}")
        for comment in comments:
            print(f"COMMENT: {comment}")
    elif args.command == "revise":
        revision_number = revise(
            connection,
            args.id,
            args.summary,
            _split_file_paths(args.files),
            diffs=_load_diffs_file(args.diffs),
        )
        if revision_number is None:
            print(f"error: PR #{args.id} is applied or does not exist")
        else:
            print(
                f"PR #{args.id} now at revision {revision_number}, status open"
            )
    elif args.command == "apply":
        result = apply_pr(connection, args.id, project_root)
        if result is None:
            print(
                f"error: PR #{args.id} is applied, closed, "
                "or does not exist"
            )
        else:
            for path in result["applied"]:
                print(f"APPLIED: {path}")
            for path in result["stale"]:
                print(f"STALE (original changed, not overwritten): {path}")
            for path in result["missing"]:
                print(f"MISSING (no shadow copy, not applied): {path}")
    elif args.command == "close":
        if close_pr(connection, args.id):
            cleanup_shadows(project_root, args.id)
            print(f"Closed PR #{args.id}")
        else:
            print(
                f"error: PR #{args.id} is applied, closed, "
                "or does not exist"
            )
    elif args.command == "comment":
        if post_comment(connection, args.id, args.body):
            print(f"Comment posted on PR #{args.id}")
        else:
            print(f"error: PR #{args.id} does not exist")
    elif args.command == "list":
        for pr in list_prs(connection):
            print(f"#{pr['id']}\t{pr['status']}\t{pr['title']}")
    connection.close()
