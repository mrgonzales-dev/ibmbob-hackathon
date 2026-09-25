"""bob-pr: present an agent plan as a GitHub-style pull request page.

Per-project only. All state lives in .bob-pr/bob_pr.db under the project root.

Commands:
  new       create a PR + revision 1 from a plan
  serve     run the localhost review server
  decision  print the verdict for a PR (APPROVED | CHANGES_REQUESTED | PENDING)
  revise    add a new revision after CHANGES_REQUESTED
  list      print all PRs and statuses
"""

import argparse
import html
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8642
DB_DIR = ".bob-pr"
DB_NAME = "bob_pr.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS prs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pr_id INTEGER NOT NULL REFERENCES prs(id),
  n INTEGER NOT NULL,
  summary TEXT NOT NULL,
  files_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pr_id INTEGER NOT NULL REFERENCES prs(id),
  revision_id INTEGER,
  kind TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
"""

KIND_TO_VERDICT = {"approve": "APPROVED", "request_changes": "CHANGES_REQUESTED"}


def _now():
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(path):
    """Open (and create if needed) the SQLite database at path.

    Creates the parent directory and applies the schema. Returns a
    sqlite3.Connection with foreign keys enabled.
    """
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def _latest_revision(conn, pr_id):
    """Return the newest revision row (id, n, summary, files_json) for a PR.

    Returns None if the PR has no revisions.
    """
    return conn.execute(
        "SELECT id, n, summary, files_json FROM revisions "
        "WHERE pr_id=? ORDER BY n DESC LIMIT 1",
        (pr_id,),
    ).fetchone()


def create_pr(conn, title, summary, files):
    """Insert a new PR (status 'open') plus revision 1.

    files is a list of paths the plan will touch. Returns the new PR id.
    """
    cur = conn.execute(
        "INSERT INTO prs (title, status, created_at) VALUES (?, 'open', ?)",
        (title, _now()),
    )
    pid = cur.lastrowid
    conn.execute(
        "INSERT INTO revisions (pr_id, n, summary, files_json, created_at) "
        "VALUES (?, 1, ?, ?, ?)",
        (pid, summary, json.dumps(files), _now()),
    )
    conn.commit()
    return pid


def record_decision(conn, pr_id, kind, body):
    """Record a user click on a decision button.

    kind is 'approve' or 'request_changes'. Stamps the event with the latest
    revision id and flips prs.status to 'approved' or 'changes_requested'.
    """
    if kind not in ("approve", "request_changes"):
        raise ValueError(f"unknown decision kind: {kind}")
    rev = _latest_revision(conn, pr_id)
    rev_id = rev[0] if rev else None
    conn.execute(
        "INSERT INTO events (pr_id, revision_id, kind, body, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (pr_id, rev_id, kind, body or "", _now()),
    )
    status = "approved" if kind == "approve" else "changes_requested"
    conn.execute("UPDATE prs SET status=? WHERE id=?", (status, pr_id))
    conn.commit()


def get_decision(conn, pr_id):
    """Return (verdict, comments) for the latest revision of a PR.

    verdict is 'APPROVED', 'CHANGES_REQUESTED', or 'PENDING'. comments is the
    list of non-empty bodies on decision events for that revision.
    """
    rev = _latest_revision(conn, pr_id)
    if not rev:
        return "PENDING", []
    rows = conn.execute(
        "SELECT kind, body FROM events WHERE pr_id=? AND revision_id=? "
        "AND kind IN ('approve','request_changes') ORDER BY id",
        (pr_id, rev[0]),
    ).fetchall()
    if not rows:
        return "PENDING", []
    verdict = KIND_TO_VERDICT[rows[-1][0]]
    comments = [body for _, body in rows if body]
    return verdict, comments


def revise(conn, pr_id, summary, files):
    """Add a new revision to a PR and set its status back to 'open'.

    Returns the new revision number.
    """
    rev = _latest_revision(conn, pr_id)
    n = (rev[1] if rev else 0) + 1
    conn.execute(
        "INSERT INTO revisions (pr_id, n, summary, files_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (pr_id, n, summary, json.dumps(files), _now()),
    )
    conn.execute("UPDATE prs SET status='open' WHERE id=?", (pr_id,))
    conn.commit()
    return n


def list_prs(conn):
    """Return all PRs as a list of dicts with id, title, status, created_at."""
    rows = conn.execute(
        "SELECT id, title, status, created_at FROM prs ORDER BY id"
    ).fetchall()
    return [
        {"id": r[0], "title": r[1], "status": r[2], "created_at": r[3]}
        for r in rows
    ]


BADGE_CLASS = {"open": "open", "approved": "approved", "changes_requested": "changes"}

PAGE_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
       margin: 0; background: #f6f8fa; color: #1f2328; }
header.top { background: #0d1117; color: #f0f6fc; padding: 12px 24px;
             font-size: 14px; }
main { max-width: 960px; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 22px; font-weight: 600; margin: 0 0 8px; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 20px;
         font-size: 13px; font-weight: 600; }
.badge.open { background: #1f883d; color: #fff; }
.badge.approved { background: #8250df; color: #fff; }
.badge.changes { background: #cf222e; color: #fff; }
.card { background: #fff; border: 1px solid #d1d9e0; border-radius: 8px;
        padding: 16px; margin-bottom: 16px; }
.card .meta { color: #59636e; font-size: 13px; margin-bottom: 8px; }
.files li { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 13px; margin: 4px 0; }
.review { position: sticky; bottom: 0; background: #fff;
          border-top: 1px solid #d1d9e0; padding: 16px 24px; }
.review textarea { width: 100%; min-height: 64px; padding: 8px;
                   border: 1px solid #d1d9e0; border-radius: 6px;
                   font: inherit; margin-bottom: 8px; }
button { padding: 8px 16px; border: none; border-radius: 6px;
         font-weight: 600; font-size: 14px; cursor: pointer; }
#btn-approve { background: #1f883d; color: #fff; }
#btn-changes { background: #cf222e; color: #fff; }
button:disabled { opacity: .5; cursor: default; }
#banner { display: none; background: #ddf4e4; border: 1px solid #1f883d;
          border-radius: 6px; padding: 10px; margin-bottom: 12px; }
a { color: #0969da; text-decoration: none; }
"""


def render_pr_page(conn, pr_id):
    """Render the GitHub-style PR review page for one PR as an HTML string."""
    pr = conn.execute(
        "SELECT title, status FROM prs WHERE id=?", (pr_id,)
    ).fetchone()
    if not pr:
        return "<h1>PR not found</h1>"
    rev = _latest_revision(conn, pr_id)
    files = json.loads(rev[3]) if rev else []
    summary = rev[2] if rev else ""
    events = conn.execute(
        "SELECT kind, body, created_at FROM events WHERE pr_id=? ORDER BY id",
        (pr_id,),
    ).fetchall()
    esc = html.escape
    badge = {"open": "Open", "approved": "Approved", "changes_requested": "Changes requested"}[pr[1]]
    timeline = "".join(
        f"<div class='card'><div class='meta'>user &middot; {esc(e[2])} &middot; {esc(e[0])}</div>{esc(e[1])}</div>"
        for e in events
    )
    file_items = "".join(
        f"<li>{esc(f)} <span class='meta'>planned change</span></li>" for f in files
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>PLAN-PR #{pr_id}</title>
<style>{PAGE_CSS}</style></head><body>
<header class="top">bob-pr &middot; PLAN-PR #{pr_id}</header>
<main>
<h1>{esc(pr[0])} <span class="badge {BADGE_CLASS[pr[1]]}">{badge}</span></h1>
<div id="banner">Decision recorded. Tell the agent you are done.</div>
<div class="card"><div class="meta">bob-agent opened this plan &middot; revision {rev[1] if rev else 0}</div>
<p>{esc(summary)}</p></div>
{timeline}
<div class="card"><div class="meta">Files changed ({len(files)})</div>
<ul class="files">{file_items}</ul></div>
</main>
<div class="review">
<textarea id="comment" placeholder="Leave a review comment (optional)"></textarea>
<button id="btn-approve" onclick="decide('approve')">Approve plan</button>
<button id="btn-changes" onclick="decide('request_changes')">Request changes</button>
</div>
<script>
async function decide(kind) {{
  const comment = document.getElementById('comment').value;
  const r = await fetch('/decision', {{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{pr_id: {pr_id}, kind, comment}})}});
  if (r.ok) {{
    document.getElementById('banner').style.display = 'block';
    document.getElementById('btn-approve').disabled = true;
    document.getElementById('btn-changes').disabled = true;
  }}
}}
</script>
</body></html>"""


def render_index_page(conn):
    """Render the PR list page (like GitHub's pull request index)."""
    rows = list_prs(conn)
    items = "".join(
        f"<li><a href='/pr/{r['id']}'>#{r['id']} {html.escape(r['title'])}</a> "
        f"<span class='badge {BADGE_CLASS[r['status']]}'>{r['status']}</span></li>"
        for r in rows
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>bob-pr</title>
<style>{PAGE_CSS}</style></head><body>
<header class="top">bob-pr &middot; pull requests</header>
<main><h1>Plan PRs</h1><ul class="files">{items}</ul></main>
</body></html>"""


def make_server(db_path, port=DEFAULT_PORT):
    """Create (but do not start) the HTTP server for the review pages.

    Routes: GET / PR list, GET /pr/<id> PR page, POST /decision record click.
    Each request opens its own SQLite connection to db_path.
    """

    class Handler(BaseHTTPRequestHandler):
        """Route requests to the PR pages and the decision endpoint."""

        def _send_html(self, body, code=200):
            """Write an HTML response with the given status code."""
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            """Serve the PR list at / and a PR page at /pr/<id>."""
            conn = init_db(self.server.db_path)
            try:
                if self.path == "/":
                    self._send_html(render_index_page(conn))
                    return
                m = re.fullmatch(r"/pr/(\d+)", self.path)
                if m:
                    self._send_html(render_pr_page(conn, int(m.group(1))))
                    return
                self._send_html("<h1>404</h1>", 404)
            finally:
                conn.close()

        def do_POST(self):
            """Record a decision click posted as JSON {pr_id, kind, comment}."""
            if self.path != "/decision":
                self._send_html("<h1>404</h1>", 404)
                return
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            conn = init_db(self.server.db_path)
            try:
                record_decision(
                    conn,
                    int(payload["pr_id"]),
                    payload["kind"],
                    payload.get("comment", ""),
                )
            finally:
                conn.close()
            self._send_html(json.dumps({"ok": True}))

        def log_message(self, *args):
            """Silence the default per-request log line."""

    server = ThreadingHTTPServer(("localhost", port), Handler)
    server.db_path = db_path
    return server


def _db_path(args):
    """Resolve the database path: --db flag, env var, or .bob-pr/ under cwd."""
    return args.db or os.environ.get(
        "BOB_PR_DB", os.path.join(os.getcwd(), DB_DIR, DB_NAME)
    )


def _split_files(value):
    """Split a comma-separated --files argument into a clean path list."""
    return [f.strip() for f in (value or "").split(",") if f.strip()]


def main(argv=None):
    """Parse CLI arguments and run the requested subcommand."""
    p = argparse.ArgumentParser(prog="bob_pr", description=__doc__)
    p.add_argument("--db", help="database path (default: .bob-pr/bob_pr.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("new", help="create a PR from a plan")
    sp.add_argument("--title", required=True)
    sp.add_argument("--summary", required=True)
    sp.add_argument("--files", default="")

    sp = sub.add_parser("serve", help="run the review server")
    sp.add_argument("--port", type=int, default=DEFAULT_PORT)

    sp = sub.add_parser("decision", help="print the verdict for a PR")
    sp.add_argument("id", type=int)

    sp = sub.add_parser("revise", help="add a new revision to a PR")
    sp.add_argument("id", type=int)
    sp.add_argument("--summary", required=True)
    sp.add_argument("--files", default="")

    sub.add_parser("list", help="list all PRs")

    args = p.parse_args(argv)
    conn = init_db(_db_path(args))

    if args.cmd == "new":
        pid = create_pr(conn, args.title, args.summary, _split_files(args.files))
        print(f"PR_ID={pid}")
        print(f"Created PLAN-PR #{pid}: {args.title}")
    elif args.cmd == "serve":
        server = make_server(_db_path(args), args.port)
        print(f"Serving on http://localhost:{server.server_address[1]}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    elif args.cmd == "decision":
        verdict, comments = get_decision(conn, args.id)
        print(f"STATUS: {verdict}")
        for c in comments:
            print(f"COMMENT: {c}")
    elif args.cmd == "revise":
        n = revise(conn, args.id, args.summary, _split_files(args.files))
        print(f"PR #{args.id} now at revision {n}, status open")
    elif args.cmd == "list":
        for r in list_prs(conn):
            print(f"#{r['id']}\t{r['status']}\t{r['title']}")
    conn.close()


if __name__ == "__main__":
    main()
