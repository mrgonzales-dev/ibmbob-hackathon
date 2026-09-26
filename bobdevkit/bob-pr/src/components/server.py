"""HTTP server: serves the review pages and records button clicks.

Routes: GET / lists PRs, GET /pr/<id> shows one PR page, POST /decision
records a click. Each request opens its own SQLite connection so threaded
requests stay independent.
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from components.database import init_db
from components.decisions import record_decision
from components.rendering import render_index_page, render_pr_page

DEFAULT_PORT = 2428


def make_server(database_path, port=DEFAULT_PORT, project_root=None):
    """Create (but do not start) the HTTP server for the review pages.

    The bind is strict: a taken port raises OSError — bob-pr serves on
    its own port (2428 by default) or not at all. project_root lets the
    pages diff live shadow copies; without it they render stored diffs.
    """

    class Handler(BaseHTTPRequestHandler):
        """Route requests to the PR pages and the decision endpoint."""

        def _send_html(self, body, code=200):
            """Write an HTML response with the given status code."""
            payload = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            """Serve the PR list at / and a PR page at /pr/<id>."""
            connection = init_db(self.server.database_path)
            try:
                if self.path == "/":
                    self._send_html(render_index_page(connection))
                    return
                match = re.fullmatch(r"/pr/(\d+)", self.path)
                if match:
                    self._send_html(
                        render_pr_page(
                            connection,
                            int(match.group(1)),
                            self.server.project_root,
                        )
                    )
                    return
                self._send_html("<h1>404</h1>", 404)
            finally:
                connection.close()

        def do_POST(self):
            """Record a decision click posted as JSON {pr_id, kind, comment}.

            Bad JSON, a missing or non-integer pr_id, and an unknown kind
            get a 400. A pr_id that no PR owns gets a 404.
            """
            if self.path != "/decision":
                self._send_html("<h1>404</h1>", 404)
                return

            def reject(code, error):
                self._send_html(json.dumps({"ok": False, "error": error}), code)

            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                reject(400, "body must be JSON")
                return
            if not isinstance(payload, dict):
                reject(400, "body must be a JSON object")
                return
            try:
                pull_request_id = int(payload["pr_id"])
            except (KeyError, TypeError, ValueError):
                reject(400, "pr_id is required")
                return
            kind = payload.get("kind")
            if kind not in ("approve", "request_changes"):
                reject(400, "kind must be approve or request_changes")
                return
            comment = payload.get("comment", "")
            if kind == "request_changes" and not str(comment).strip():
                reject(400, "request_changes requires a comment")
                return
            connection = init_db(self.server.database_path)
            try:
                exists = connection.execute(
                    "SELECT 1 FROM prs WHERE id=?", (pull_request_id,)
                ).fetchone()
                if exists is None:
                    reject(404, "unknown PR")
                    return
                record_decision(connection, pull_request_id, kind, comment)
            finally:
                connection.close()
            self._send_html(json.dumps({"ok": True}))

        def log_message(self, *args):
            """Silence the default per-request log line."""

    server = ThreadingHTTPServer(("localhost", port), Handler)
    server.database_path = database_path
    server.project_root = project_root
    return server
