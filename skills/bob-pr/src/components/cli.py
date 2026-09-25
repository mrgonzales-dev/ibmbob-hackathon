"""Command-line interface: the verbs the agent calls between review steps.

Commands: new, snapshot, diff, serve, decision, revise, apply, list.
All state lives in .bob-pr/bob_pr.db under the current project root.
"""

import argparse
import json
import os

from components.database import init_db
from components.decisions import get_decision
from components.pull_requests import create_pr, list_prs, revise
from components.server import DEFAULT_PORT, make_server
from components.snapshots import apply_pr, compute_diffs, snapshot_pr

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

    serve_cmd = subcommands.add_parser("serve", help="run the review server")
    serve_cmd.add_argument("--port", type=int, default=DEFAULT_PORT)

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
    elif args.command == "diff":
        diffs = compute_diffs(connection, args.id, project_root)
        changed = [p for p, d in diffs.items() if d]
        print(f"Diffs stored for {len(changed)} changed file(s): {changed}")
    elif args.command == "serve":
        server = make_server(_database_path(args), args.port)
        print(f"Serving on http://localhost:{server.server_address[1]}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
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
        print(f"PR #{args.id} now at revision {revision_number}, status open")
    elif args.command == "apply":
        result = apply_pr(connection, args.id, project_root)
        for path in result["applied"]:
            print(f"APPLIED: {path}")
        for path in result["stale"]:
            print(f"STALE (original changed, not overwritten): {path}")
    elif args.command == "list":
        for pr in list_prs(connection):
            print(f"#{pr['id']}\t{pr['status']}\t{pr['title']}")
    connection.close()
