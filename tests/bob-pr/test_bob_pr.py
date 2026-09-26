# Run from the repo root:  python3 bob-pr/src/test_bob_pr.py
"""Tests for bob_pr.py. Run: python3 test_bob_pr.py (from src/, or python3 -m unittest)."""

import contextlib
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
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

    def test_revise_on_applied_pr_is_refused(self):
        """revise must refuse an applied PR: the audit record is immutable.
        It returns None, leaves the status at 'applied', and adds no
        revision."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        self.conn.execute(
            "UPDATE prs SET status='applied' WHERE id=?", (pid,)
        )
        n = bob_pr.revise(self.conn, pid, "S2", ["b.py"])
        self.assertIsNone(n)
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "applied")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM revisions WHERE pr_id=?", (pid,)
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_revise_on_unknown_pr_is_refused(self):
        """revise must refuse a PR id that does not exist instead of
        crashing on the revisions.pr_id foreign key."""
        n = bob_pr.revise(self.conn, 999, "S", ["a.py"])
        self.assertIsNone(n)

    def test_get_decision_on_unknown_pr_is_unknown(self):
        """get_decision must report UNKNOWN for a PR id that does not
        exist, so the CLI never prints PENDING for nothing."""
        status, comments = bob_pr.get_decision(self.conn, 999)
        self.assertEqual(status, "UNKNOWN")
        self.assertEqual(comments, [])

    def test_close_sets_status_and_event(self):
        """close_pr must set status 'closed' and write a 'closed' event,
        so a rejected plan leaves the Open list."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        ok = bob_pr.close_pr(self.conn, pid)
        self.assertTrue(ok)
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "closed")
        ev = self.conn.execute(
            "SELECT kind FROM events WHERE pr_id=? AND kind='closed'",
            (pid,),
        ).fetchone()
        self.assertIsNotNone(ev)

    def test_close_on_applied_pr_is_refused(self):
        """close_pr must refuse an applied PR: applied stays applied."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        self.conn.execute(
            "UPDATE prs SET status='applied' WHERE id=?", (pid,)
        )
        ok = bob_pr.close_pr(self.conn, pid)
        self.assertFalse(ok)
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "applied")

    def test_close_on_unknown_pr_is_refused(self):
        """close_pr must refuse a PR id that does not exist."""
        self.assertFalse(bob_pr.close_pr(self.conn, 999))

    def test_decision_on_closed_pr_is_ignored(self):
        """record_decision on a closed PR must write no event and leave
        the status at 'closed' — closed is terminal like applied."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.close_pr(self.conn, pid)
        bob_pr.record_decision(self.conn, pid, "approve", "too late")
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "closed")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE pr_id=? AND kind='approve'",
            (pid,),
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_revise_on_closed_pr_is_refused(self):
        """revise must refuse a closed PR the same way it refuses an
        applied one."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.close_pr(self.conn, pid)
        n = bob_pr.revise(self.conn, pid, "S2", ["b.py"])
        self.assertIsNone(n)
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "closed")

    def test_closed_pr_page_is_read_only(self):
        """A closed PR page must show the Closed badge and no decision
        buttons — it is a read-only record of a rejected plan."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.close_pr(self.conn, pid)
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("Closed", html)
        self.assertNotIn('id="btn-approve"', html)

    def test_unknown_status_renders_without_crash(self):
        """A status the badge maps do not know must still render: the
        badge falls back to the raw status text instead of KeyError."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        self.conn.execute(
            "UPDATE prs SET status='mystery' WHERE id=?", (pid,)
        )
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("mystery", html)
        index = bob_pr.render_index_page(self.conn)
        self.assertIn("mystery", index)

    def test_index_separates_closed_prs(self):
        """render_index_page must keep closed PRs out of the Open list
        and group them under their own Closed section."""
        bob_pr.create_pr(self.conn, "P-open", "S", ["a.py"])
        closed_pid = bob_pr.create_pr(self.conn, "P-closed", "S", ["b.py"])
        bob_pr.close_pr(self.conn, closed_pid)
        html = bob_pr.render_index_page(self.conn)
        self.assertIn("<h2>Closed</h2>", html)
        self.assertLess(html.index("P-open"), html.index("<h2>Closed</h2>"))
        self.assertGreater(html.index("P-closed"), html.index("<h2>Closed</h2>"))

    def test_comment_posts_event_without_verdict(self):
        """post_comment must write a 'comment' event on the latest
        revision and must not move the verdict off PENDING."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        ok = bob_pr.post_comment(self.conn, pid, "waiting on CI")
        self.assertTrue(ok)
        ev = self.conn.execute(
            "SELECT kind, body FROM events WHERE pr_id=? AND kind='comment'",
            (pid,),
        ).fetchone()
        self.assertEqual(ev, ("comment", "waiting on CI"))
        status, _ = bob_pr.get_decision(self.conn, pid)
        self.assertEqual(status, "PENDING")

    def test_comment_on_unknown_pr_is_refused(self):
        """post_comment must refuse a PR id that does not exist."""
        self.assertFalse(bob_pr.post_comment(self.conn, 999, "hi"))

    def test_timeline_labels_actor_by_event_kind(self):
        """The timeline must label each event with its actor: user for
        decisions, agent for comments, bob-pr for lifecycle events."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.post_comment(self.conn, pid, "note from the agent")
        bob_pr.record_decision(self.conn, pid, "approve", "ok")
        bob_pr.close_pr(self.conn, pid)
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("agent &middot;", html)
        self.assertIn("user &middot;", html)
        self.assertIn("bob-pr &middot;", html)

    def test_revise_inherits_files_when_omitted(self):
        """revise with an empty file list must inherit the previous
        revision's files, never write an empty files_json."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py", "b.py"])
        bob_pr.revise(self.conn, pid, "S2", [])
        row = self.conn.execute(
            "SELECT files_json FROM revisions WHERE pr_id=? AND n=2",
            (pid,),
        ).fetchone()
        self.assertEqual(json.loads(row[0]), ["a.py", "b.py"])

    def test_diff_warns_on_empty_file_list(self):
        """diff on a revision with no planned files must print a
        warning naming the problem, not a misleading '0 changed'."""
        pid = bob_pr.create_pr(self.conn, "T", "S", [])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bob_pr.main(["--db", self.db_path, "diff", str(pid)])
        self.assertIn("no planned files", output.getvalue())

    def test_approve_locks_the_verdict(self):
        """Once a PR is approved, later decision clicks are ignored:
        no new event, status stays 'approved', verdict stays APPROVED."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.record_decision(self.conn, pid, "approve", "")
        bob_pr.record_decision(self.conn, pid, "request_changes", "nope")
        status, _comments = bob_pr.get_decision(self.conn, pid)
        self.assertEqual(status, "APPROVED")
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "approved")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE pr_id=? "
            "AND kind IN ('approve','request_changes')",
            (pid,),
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_approved_pr_page_hides_decision_buttons(self):
        """An approved PR page must not render the decision buttons —
        approval is final and the page shows a waiting note instead."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        bob_pr.record_decision(self.conn, pid, "approve", "")
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertNotIn('id="btn-approve"', html)
        self.assertIn("Approved", html)

    def test_pr_page_blocks_decision_without_diffs(self):
        """A PR with no computed diffs must render the decision buttons
        disabled behind a warning — nothing can be approved
        sight-unseen."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn('id="btn-approve" disabled', html)
        self.assertIn("No diffs", html)

    def test_decide_redirects_and_shows_toast(self):
        """After a decision click the page must navigate back to the PR
        page carrying a hash, and the page must ship toast JS that reads
        the hash and tells the user to inform the agent."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["a.py"])
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("location.hash", html)
        self.assertIn("tell your agent", html)
        self.assertIn(f"/pr/{pid}#", html)

    def test_record_decision_on_unknown_pr_is_ignored(self):
        """record_decision on a PR id that does not exist must write no
        event and must not crash on the events.pr_id foreign key."""
        bob_pr.record_decision(self.conn, 999, "approve", "hi")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE pr_id=999"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_list_returns_all_prs(self):
        """list_prs must return every PR as a dict with at least title and status."""
        bob_pr.create_pr(self.conn, "P1", "S", ["a.py"])
        bob_pr.create_pr(self.conn, "P2", "S", ["b.py"])
        prs = bob_pr.list_prs(self.conn)
        self.assertEqual(len(prs), 2)
        self.assertEqual(prs[0]["title"], "P1")
        self.assertEqual(prs[1]["title"], "P2")

    def test_render_shows_diff_hunks(self):
        """render_pr_page must show per-file diff hunks with + and - lines
        marked as additions and deletions."""
        pid = bob_pr.create_pr(
            self.conn, "T", "S", ["a.py"],
            diffs={"a.py": "+new line\n-old line\n context"},
        )
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("diff-add", html)
        self.assertIn("diff-del", html)
        self.assertIn("+new line", html)
        self.assertIn("-old line", html)

    def test_revise_updates_diffs(self):
        """revise must store new diff data on the new revision so the page
        shows the latest diffs, not the old ones."""
        pid = bob_pr.create_pr(
            self.conn, "T", "S", ["a.py"], diffs={"a.py": "+v1"}
        )
        bob_pr.revise(self.conn, pid, "S2", ["a.py"], diffs={"a.py": "+v2"})
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("+v2", html)
        self.assertNotIn("+v1", html)

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


class SnapshotTests(unittest.TestCase):
    """Tests for the shadow-copy workflow: snapshot, computed diff, apply."""

    def setUp(self):
        """Create a temp project root with a real source file and a database."""
        self.root = tempfile.mkdtemp()
        self._write("src/a.py", "line one\nline two\n")
        self.db_path = os.path.join(self.root, ".bob-pr", "bob_pr.db")
        self.conn = bob_pr.init_db(self.db_path)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def _write(self, rel, content):
        """Write content to a file inside the temp project root."""
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def _read(self, rel):
        """Read a file inside the temp project root."""
        with open(os.path.join(self.root, rel)) as f:
            return f.read()

    def _tmp_path(self, pid, rel):
        """Return the shadow-copy path for a file under a PR."""
        return os.path.join(self.root, ".bob-pr", "tmp", str(pid), rel)

    def test_snapshot_copies_files_and_records_hash(self):
        """snapshot_pr must copy each planned file to .bob-pr/tmp/<id>/ and
        record a sha256 per file; missing files get a null hash."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py", "src/new.py"])
        manifest = bob_pr.snapshot_pr(self.conn, pid, self.root)
        self.assertEqual(self._read(self._tmp_path(pid, "src/a.py")),
                         "line one\nline two\n")
        self.assertEqual(
            manifest["src/a.py"]["sha256"],
            hashlib.sha256(b"line one\nline two\n").hexdigest(),
        )
        self.assertIsNone(manifest["src/new.py"]["sha256"])

    def test_diff_computes_unified_diff(self):
        """compute_diffs must store a real unified diff of the edited copy
        vs the original on the latest revision."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "line one\nline CHANGED\n")
        diffs = bob_pr.compute_diffs(self.conn, pid, self.root)
        self.assertIn("-line two", diffs["src/a.py"])
        self.assertIn("+line CHANGED", diffs["src/a.py"])

    def test_diff_new_file_is_all_additions(self):
        """compute_diffs must diff a brand-new copy against an empty original,
        so every line renders as an addition."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/new.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/new.py"), "fresh line\n")
        diffs = bob_pr.compute_diffs(self.conn, pid, self.root)
        self.assertIn("+fresh line", diffs["src/new.py"])
        deleted = [
            line for line in diffs["src/new.py"].splitlines()
            if line.startswith("-") and not line.startswith("---")
        ]
        self.assertEqual(deleted, [])

    def test_apply_writes_approved_edits_atomically(self):
        """apply_pr must install the shadow copy over the real file and
        record an 'applied' event."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "new content\n")
        result = bob_pr.apply_pr(self.conn, pid, self.root)
        self.assertEqual(self._read("src/a.py"), "new content\n")
        self.assertIn("src/a.py", result["applied"])
        ev = self.conn.execute(
            "SELECT kind FROM events WHERE pr_id=? AND kind='applied'", (pid,)
        ).fetchone()
        self.assertIsNotNone(ev)

    def test_apply_skips_stale_file(self):
        """apply_pr must refuse to overwrite a file the user changed after
        the snapshot and must report it as stale."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "agent version\n")
        self._write("src/a.py", "user edited me\n")
        result = bob_pr.apply_pr(self.conn, pid, self.root)
        self.assertIn("src/a.py", result["stale"])
        self.assertNotIn("src/a.py", result["applied"])
        self.assertEqual(self._read("src/a.py"), "user edited me\n")

    def test_apply_uses_current_revision_files(self):
        """apply_pr must install exactly the files of the latest revision:
        files dropped by a revise are skipped, and files added by a revise
        are installed even without a fresh snapshot."""
        self._write("src/b.py", "b\n")
        pid = bob_pr.create_pr(
            self.conn, "T", "S", ["src/a.py", "src/b.py"]
        )
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "a edited\n")
        self._write(self._tmp_path(pid, "src/b.py"), "b edited\n")
        bob_pr.revise(self.conn, pid, "S2", ["src/a.py", "src/c.py"])
        self._write(self._tmp_path(pid, "src/c.py"), "c new\n")
        result = bob_pr.apply_pr(self.conn, pid, self.root)
        self.assertIn("src/a.py", result["applied"])
        self.assertIn("src/c.py", result["applied"])
        self.assertNotIn("src/b.py", result["applied"])
        self.assertEqual(self._read("src/b.py"), "b\n")

    def test_apply_marks_pr_applied(self):
        """apply_pr must set prs.status to 'applied' when every planned file
        lands without a stale file."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "final\n")
        bob_pr.apply_pr(self.conn, pid, self.root)
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "applied")

    def test_applied_pr_page_is_read_only(self):
        """An applied PR page must show an audit banner and no decision
        buttons, so it cannot be acted on again."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "final\n")
        bob_pr.apply_pr(self.conn, pid, self.root)
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("read-only", html)
        self.assertNotIn('id="btn-approve"', html)

    def test_decision_on_applied_pr_is_ignored(self):
        """record_decision on an applied PR must be a no-op so a finished PR
        stays a pure audit snapshot."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "final\n")
        bob_pr.apply_pr(self.conn, pid, self.root)
        bob_pr.record_decision(self.conn, pid, "request_changes", "too late")
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "applied")

    def test_apply_creates_new_file(self):
        """apply_pr must create files that did not exist at snapshot time."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/new.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/new.py"), "created\n")
        result = bob_pr.apply_pr(self.conn, pid, self.root)
        self.assertIn("src/new.py", result["applied"])
        self.assertEqual(self._read("src/new.py"), "created\n")

    def test_apply_reports_missing_shadow_copy(self):
        """apply_pr must list a planned file that has no shadow copy under
        'missing', and must not mark the PR applied while a planned file
        never landed."""
        pid = bob_pr.create_pr(
            self.conn, "T", "S", ["src/a.py", "src/gone.py"]
        )
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "new content\n")
        result = bob_pr.apply_pr(self.conn, pid, self.root)
        self.assertIn("src/gone.py", result["missing"])
        self.assertIn("src/a.py", result["applied"])
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "open")

    def test_apply_cleans_shadow_dir(self):
        """apply_pr must remove .bob-pr/tmp/<id>/ once every planned file
        lands, so shadow copies do not accumulate forever."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "final\n")
        bob_pr.apply_pr(self.conn, pid, self.root)
        shadow_dir = os.path.join(self.root, ".bob-pr", "tmp", str(pid))
        self.assertFalse(os.path.exists(shadow_dir))

    def test_apply_keeps_shadow_dir_when_files_stale(self):
        """apply_pr must keep the shadow dir when a file went stale, so
        the agent can retry after re-snapshotting."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "agent version\n")
        self._write("src/a.py", "user edited me\n")
        bob_pr.apply_pr(self.conn, pid, self.root)
        shadow_dir = os.path.join(self.root, ".bob-pr", "tmp", str(pid))
        self.assertTrue(os.path.exists(shadow_dir))

    def test_cleanup_shadows_removes_dir(self):
        """cleanup_shadows must remove .bob-pr/tmp/<id>/ entirely, for
        the close path that has no apply."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        bob_pr.cleanup_shadows(self.root, pid)
        shadow_dir = os.path.join(self.root, ".bob-pr", "tmp", str(pid))
        self.assertFalse(os.path.exists(shadow_dir))

    def test_apply_on_terminal_pr_is_refused(self):
        """apply_pr must refuse a closed or applied PR: it returns None
        and writes nothing."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "agent version\n")
        bob_pr.close_pr(self.conn, pid)
        result = bob_pr.apply_pr(self.conn, pid, self.root)
        self.assertIsNone(result)
        self.assertEqual(self._read("src/a.py"), "line one\nline two\n")
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "closed")

    def test_snapshot_keeps_edited_copies(self):
        """A re-snapshot must not clobber a shadow copy that has edits:
        the copy survives and the manifest marks it kept_edits."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "agent edits\n")
        manifest = bob_pr.snapshot_pr(self.conn, pid, self.root)
        self.assertEqual(self._read(self._tmp_path(pid, "src/a.py")),
                         "agent edits\n")
        self.assertTrue(manifest["src/a.py"]["kept_edits"])

    def test_pr_page_computes_diffs_at_render_time(self):
        """render_pr_page with a project root must diff the live shadow
        copies, so edits made after `diff` still show on the page."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "line one\nline v2\n")
        bob_pr.compute_diffs(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "line one\nline v3\n")
        html = bob_pr.render_pr_page(self.conn, pid, self.root)
        self.assertIn("+line v3", html)
        self.assertNotIn("+line v2", html)

    def test_pr_page_falls_back_to_stored_diffs(self):
        """render_pr_page without a project root must render the stored
        diffs, so the CLI/test path keeps working."""
        pid = bob_pr.create_pr(
            self.conn, "T", "S", ["src/a.py"],
            diffs={"src/a.py": "+stored line\n"},
        )
        html = bob_pr.render_pr_page(self.conn, pid)
        self.assertIn("+stored line", html)

    def test_applied_pr_page_keeps_diffs_after_cleanup(self):
        """apply_pr must store the applied diff before it deletes the
        shadow dir, so the audit page still shows what landed."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/a.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        self._write(self._tmp_path(pid, "src/a.py"), "line one\nline final\n")
        bob_pr.apply_pr(self.conn, pid, self.root)
        html = bob_pr.render_pr_page(self.conn, pid, self.root)
        self.assertIn("+line final", html)

    def test_missing_shadow_copy_shows_no_changes(self):
        """A planned file with no shadow copy must render 'no changes
        yet', not a misleading all-deletions diff."""
        pid = bob_pr.create_pr(self.conn, "T", "S", ["src/gone.py"])
        bob_pr.snapshot_pr(self.conn, pid, self.root)
        html = bob_pr.render_pr_page(self.conn, pid, self.root)
        self.assertIn("no changes yet", html)
        self.assertNotIn("class='line diff-del'", html)


class ServerTests(unittest.TestCase):
    """Tests for the HTTP layer: serving pages and recording button clicks."""

    def setUp(self):
        """Boot the bob-pr server on a free OS-assigned port in a daemon thread."""
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "bob_pr.db")
        self.conn = bob_pr.init_db(self.db_path)
        self.pid = bob_pr.create_pr(
            self.conn, "T", "S", ["a.py"],
            diffs={"a.py": "--- a.py\n+++ a.py\n@@ -1 +1 @@\n-x\n+y\n"},
        )
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

    def test_review_buttons_follow_comment_state(self):
        """The page must ship the Request changes button disabled and the
        Approve button enabled, with JS that swaps the states as the user
        types a comment."""
        html = bob_pr.render_pr_page(self.conn, self.pid)
        approve_tag = '<button id="btn-approve"'
        changes_tag = '<button id="btn-changes"'
        self.assertIn(approve_tag, html)
        self.assertIn(changes_tag, html)
        approve_line = next(l for l in html.splitlines() if approve_tag in l)
        changes_line = next(l for l in html.splitlines() if changes_tag in l)
        self.assertNotIn("disabled", approve_line)
        self.assertIn("disabled", changes_line)
        self.assertIn("oninput", html)

    def test_post_request_changes_requires_comment(self):
        """POST /decision with request_changes and an empty comment must be
        rejected with 400 and must not change the PR status."""
        body = json.dumps(
            {"pr_id": self.pid, "kind": "request_changes", "comment": ""}
        ).encode()
        req = urllib.request.Request(
            f"http://localhost:{self.port}/decision",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)
        row = self.conn.execute(
            "SELECT status FROM prs WHERE id=?", (self.pid,)
        ).fetchone()
        self.assertEqual(row[0], "open")

    def test_post_decision_bad_json_gets_400(self):
        """POST /decision with a body that is not JSON must get a 400,
        not a dropped connection."""
        req = urllib.request.Request(
            f"http://localhost:{self.port}/decision",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_post_decision_missing_pr_id_gets_400(self):
        """POST /decision without pr_id must get a 400."""
        body = json.dumps({"kind": "approve", "comment": ""}).encode()
        req = urllib.request.Request(
            f"http://localhost:{self.port}/decision",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_post_decision_bad_kind_gets_400(self):
        """POST /decision with a kind that is not approve or
        request_changes must get a 400, not a crashed handler."""
        body = json.dumps(
            {"pr_id": self.pid, "kind": "bogus", "comment": ""}
        ).encode()
        req = urllib.request.Request(
            f"http://localhost:{self.port}/decision",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_post_decision_unknown_pr_gets_404(self):
        """POST /decision for a PR id that does not exist must get a 404
        and write no event."""
        body = json.dumps(
            {"pr_id": 999, "kind": "approve", "comment": ""}
        ).encode()
        req = urllib.request.Request(
            f"http://localhost:{self.port}/decision",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 404)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE pr_id=999"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_serve_fails_when_port_taken(self):
        """make_server must raise OSError when the requested port is
        already bound — bob-pr serves on its port or not at all."""
        blocker = socket.socket()
        blocker.bind(("localhost", 0))
        blocker.listen(1)
        taken_port = blocker.getsockname()[1]
        try:
            with self.assertRaises(OSError):
                bob_pr.make_server(self.db_path, port=taken_port)
        finally:
            blocker.close()

    def test_background_serve_responds_and_stop_kills_it(self):
        """serve must spawn a detached server and return immediately:
        the port file records the real port, the page answers 200, and
        stop kills the child and removes the pid file."""
        root = tempfile.mkdtemp()
        db_path = os.path.join(root, ".bob-pr", "bob_pr.db")
        bob_pr.init_db(db_path).close()
        state_dir = os.path.dirname(db_path)
        try:
            bob_pr.main(["--db", db_path, "serve", "--port", "0"])
            port_path = os.path.join(state_dir, "serve.port")
            self.assertTrue(os.path.exists(port_path))
            with open(port_path) as handle:
                port = int(handle.read().strip())
            resp = urllib.request.urlopen(f"http://localhost:{port}/")
            self.assertEqual(resp.status, 200)
        finally:
            bob_pr.main(["--db", db_path, "stop"])
        self.assertFalse(
            os.path.exists(os.path.join(state_dir, "serve.pid"))
        )

    def test_serve_replaces_a_running_server(self):
        """serve on a DB with a live server kills the old one and
        respawns — one bob-pr server at a time, always."""
        root = tempfile.mkdtemp()
        db_path = os.path.join(root, ".bob-pr", "bob_pr.db")
        bob_pr.init_db(db_path).close()
        state_dir = os.path.dirname(db_path)
        pid_path = os.path.join(state_dir, "serve.pid")
        try:
            bob_pr.main(["--db", db_path, "serve", "--port", "0"])
            with open(pid_path) as handle:
                old_pid = int(handle.read().strip())
            bob_pr.main(["--db", db_path, "serve", "--port", "0"])
            with open(pid_path) as handle:
                new_pid = int(handle.read().strip())
            self.assertNotEqual(old_pid, new_pid)

            def old_still_serving():
                try:
                    with open(f"/proc/{old_pid}/cmdline", "rb") as h:
                        return b"bob_pr.py" in h.read()
                except OSError:
                    return False

            deadline = time.time() + 5
            while old_still_serving() and time.time() < deadline:
                time.sleep(0.1)
            self.assertFalse(old_still_serving())
        finally:
            bob_pr.main(["--db", db_path, "stop"])

    def test_serve_kills_other_bob_pr_servers(self):
        """serve must SIGTERM other running bob-pr servers — including
        orphans with no pid file — before binding."""
        root = tempfile.mkdtemp()
        db_path = os.path.join(root, ".bob-pr", "bob_pr.db")
        bob_pr.init_db(db_path).close()
        script = os.path.join(
            os.path.dirname(os.path.abspath(bob_pr.__file__)), "bob_pr.py"
        )
        orphan = subprocess.Popen(
            [
                sys.executable, script,
                "--db", db_path, "serve", "--foreground", "--port", "0",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(0.5)
        try:
            bob_pr.main(["--db", db_path, "serve", "--port", "0"])
            deadline = time.time() + 5
            while orphan.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            self.assertIsNotNone(orphan.poll())
        finally:
            orphan.kill()
            orphan.wait()
            bob_pr.main(["--db", db_path, "stop"])

    def test_stop_without_server_is_clean(self):
        """stop with no pid file must report cleanly, not crash."""
        root = tempfile.mkdtemp()
        db_path = os.path.join(root, ".bob-pr", "bob_pr.db")
        bob_pr.init_db(db_path).close()
        bob_pr.main(["--db", db_path, "stop"])

    def test_get_pr_page_serves_html(self):
        """GET /pr/<id> must return HTTP 200 with the rendered PR page."""
        resp = urllib.request.urlopen(f"http://localhost:{self.port}/pr/{self.pid}")
        self.assertEqual(resp.status, 200)
        self.assertIn(b"PLAN-PR", resp.read())


if __name__ == "__main__":
    unittest.main()
