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

DEFAULT_PORT = 8642


def make_server(database_path, port=DEFAULT_PORT):
    """Create (but do not start) the HTTP server for the review pages."""

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
                        render_pr_page(connection, int(match.group(1)))
                    )
                    return
                self._send_html("<h1>404</h1>", 404)
            finally:
                connection.close()

        def do_POST(self):
            """Record a decision click posted as JSON {pr_id, kind, comment}."""
            if self.path != "/decision":
                self._send_html("<h1>404</h1>", 404)
                return
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            connection = init_db(self.server.database_path)
            try:
                record_decision(
                    connection,
                    int(payload["pr_id"]),
                    payload["kind"],
                    payload.get("comment", ""),
                )
            finally:
                connection.close()
            self._send_html(json.dumps({"ok": True}))

        def log_message(self, *args):
            """Silence the default per-request log line."""

    server = ThreadingHTTPServer(("localhost", port), Handler)
    server.database_path = database_path
    return server
