"""Tests for bob_pr.py. Run: python3 test_bob_pr.py (from src/, or python3 -m unittest)."""

import json
import os
import sys
import tempfile
import unittest
import urllib.request
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bob_pr


class DbTests(unittest.TestCase):
    """Tests for the data layer: schema, PR records, decisions, revisions."""

    def setUp(self):
        """Create a temp directory and a fresh SQLite database for each test."""
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "bob_pr.db")
        self.conn = bob_pr.init_db(self.db_path)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_new_creates_pr_open_with_revision_1(self):
        """create_pr must insert a PR with status 'open' and revision 1
        carrying the given summary and file list."""
        pid = bob_pr.create_pr(
            self.conn, "Add limiter", "Cap login at 5/min", ["src/auth.py", "src/middleware.py"]
        )
        row = self.conn.execute(
            "SELECT title, status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row, ("Add limiter", "open"))
        rev = self.conn.execute(
            "SELECT n, summary, files_json FROM revisions WHERE pr_id=?", (pid,)
        ).fetchone()
        self.assertEqual(rev[0], 1)
        self.assertEqual(rev[1], "Cap login at 5/min")
        self.assertEqual(json.loads(rev[2]), ["src/auth.py", "src/middleware.py"])

    def test_decision_pending_initially(self):
        """get_decision must return PENDING with no comments before any click."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        status, comments = bob_pr.get_decision(self.conn, pid)
        self.assertEqual(status, "PENDING")
        self.assertEqual(comments, [])

    def test_approve_sets_status_and_comment(self):
        """record_decision('approve') must set the PR status to 'approved'
        and return verdict APPROVED with the user's comment."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.record_decision(self.conn, pid, "approve", "looks good")
        status, comments = bob_pr.get_decision(self.conn, pid)
        self.assertEqual(status, "APPROVED")
        self.assertEqual(comments, ["looks good"])
        row = self.conn.execute("SELECT status FROM prs WHERE id=?", (pid,)).fetchone()
        self.assertEqual(row[0], "approved")

    def test_request_changes_sets_status_and_comment(self):
        """record_decision('request_changes') must set the PR status to
        'changes_requested' and return verdict CHANGES_REQUESTED."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.record_decision(self.conn, pid, "request_changes", "also cover auth.py")
        status, comments = bob_pr.get_decision(self.conn, pid)
        self.assertEqual(status, "CHANGES_REQUESTED")
        self.assertEqual(comments, ["also cover auth.py"])
        row = self.conn.execute("SELECT status FROM prs WHERE id=?", (pid,)).fetchone()
        self.assertEqual(row[0], "changes_requested")

    def test_revise_adds_revision_2_and_reopens(self):
        """revise must insert revision 2 with the new plan data and flip the
        PR status back to 'open' for re-review."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.record_decision(self.conn, pid, "request_changes", "fix it")
        n = bob_pr.revise(self.conn, pid, "S2", ["a.py", "b.py"])
        self.assertEqual(n, 2)
        row = self.conn.execute("SELECT status FROM prs WHERE id=?", (pid,)).fetchone()
        self.assertEqual(row[0], "open")
        rev = self.conn.execute(
            "SELECT summary, files_json FROM revisions WHERE pr_id=? AND n=2", (pid,)
        ).fetchone()
        self.assertEqual(rev[0], "S2")
        self.assertEqual(json.loads(rev[1]), ["a.py", "b.py"])

    def test_list_returns_all_prs(self):
        """list_prs must return every PR as a dict with at least title and status."""
        bob_pr.create_pr(self.conn, "P1", "S", ["a.py"])
        bob_pr.create_pr(self.conn, "P2", "S", ["b.py"])
        prs = bob_pr.list_prs(self.conn)
        self.assertEqual(len(prs), 2)
        self.assertEqual(prs[0]["title"], "P1")
        self.assertEqual(prs[1]["title"], "P2")

    def test_render_contains_title_badge_and_files(self):
        """render_pr_page must emit HTML containing the PLAN-PR badge, the PR
        title, the file names, and both decision buttons."""
        pid = bob_pr.create_pr(self.conn, "Add limiter", "S", ["a.py"])
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("PLAN-PR", html)
        self.assertIn("Add limiter", html)
        self.assertIn("a.py", html)
        self.assertIn("Approve", html)
        self.assertIn("Request changes", html)


class ServerTests(unittest.TestCase):
    """Tests for the HTTP layer: serving pages and recording button clicks."""

    def setUp(self):
        """Boot the bob-pr server on a free OS-assigned port in a daemon thread."""
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "bob_pr.db")
        self.conn = bob_pr.init_db(self.db_path)
        self.pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        self.server = bob_pr.make_server(self.db_path, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        """Stop the server and close the database connection."""
        self.server.shutdown()
        self.conn.close()

    def test_post_decision_writes_event_and_updates_status(self):
        """POST /decision with an approve payload must record the event so a
        second connection sees verdict APPROVED with the comment."""
        body = json.dumps({"pr_id": self.pid, "kind": "approve", "comment": "go"}).encode()
        req = urllib.request.Request(
            f"http://localhost:{self.port}/decision",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        conn2 = bob_pr.init_db(self.db_path)
        status, comments = bob_pr.get_decision(conn2, self.pid)
        self.assertEqual(status, "APPROVED")
        self.assertEqual(comments, ["go"])
        conn2.close()

    def test_get_pr_page_serves_html(self):
        """GET /pr/<id> must return HTTP 200 with the rendered PR page."""
        resp = urllib.request.urlopen(f"http://localhost:{self.port}/pr/{self.pid}")
        self.assertEqual(resp.status, 200)
        self.assertIn(b"PLAN-PR", resp.read())


if __name__ == "__main__":
    unittest.main()
