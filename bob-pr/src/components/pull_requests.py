"""Pull request records: creating PRs, adding revisions, listing.

A PR represents one plan under review. A revision is one version of that
plan; every 'request changes' cycle produces a new revision.
"""

import json
from datetime import datetime, timezone

TERMINAL_STATUSES = ("applied", "closed")


def utc_now():
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def latest_revision(connection, pull_request_id):
    """Return the newest revision row for a PR.

    The row is (id, revision_number, summary, files_json, diffs_json).
    Returns None when the PR has no revisions.
    """
    return connection.execute(
        "SELECT id, n, summary, files_json, diffs_json FROM revisions "
        "WHERE pr_id=? ORDER BY n DESC LIMIT 1",
        (pull_request_id,),
    ).fetchone()


def create_pr(connection, title, summary, file_paths, diffs=None):
    """Insert a new PR with status 'open' plus revision 1.

    file_paths is a list of project-relative paths the plan will touch.
    diffs is an optional {path: diff_text} mapping for hand-written diffs;
    computed diffs from snapshots overwrite it later. Returns the new PR id.
    """
    cursor = connection.execute(
        "INSERT INTO prs (title, status, created_at) VALUES (?, 'open', ?)",
        (title, utc_now()),
    )
    pull_request_id = cursor.lastrowid
    connection.execute(
        "INSERT INTO revisions "
        "(pr_id, n, summary, files_json, diffs_json, created_at) "
        "VALUES (?, 1, ?, ?, ?, ?)",
        (
            pull_request_id,
            summary,
            json.dumps(file_paths),
            json.dumps(diffs) if diffs else None,
            utc_now(),
        ),
    )
    connection.commit()
    return pull_request_id


def revise(connection, pull_request_id, summary, file_paths, diffs=None):
    """Add a new revision to a PR and set its status back to 'open'.

    Used after a CHANGES_REQUESTED verdict so the user can re-review.
    When file_paths is empty, the previous revision's file list is
    inherited so the caller never has to repeat it.
    Returns the new revision number, or None when the PR does not exist
    or is terminal — applied and closed PRs are immutable records.
    """
    row = connection.execute(
        "SELECT status FROM prs WHERE id=?", (pull_request_id,)
    ).fetchone()
    if row is None or row[0] in TERMINAL_STATUSES:
        return None
    revision = latest_revision(connection, pull_request_id)
    if not file_paths and revision:
        file_paths = json.loads(revision[3])
    revision_number = (revision[1] if revision else 0) + 1
    connection.execute(
        "INSERT INTO revisions "
        "(pr_id, n, summary, files_json, diffs_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            pull_request_id,
            revision_number,
            summary,
            json.dumps(file_paths),
            json.dumps(diffs) if diffs else None,
            utc_now(),
        ),
    )
    connection.execute(
        "UPDATE prs SET status='open' WHERE id=?", (pull_request_id,)
    )
    connection.commit()
    return revision_number


def close_pr(connection, pull_request_id):
    """Set a PR's status to 'closed' and record a 'closed' event.

    A closed PR is a rejected or abandoned plan leaving the Open list.
    Returns False when the PR does not exist or is already terminal —
    applied and closed PRs are immutable records.
    """
    row = connection.execute(
        "SELECT status FROM prs WHERE id=?", (pull_request_id,)
    ).fetchone()
    if row is None or row[0] in TERMINAL_STATUSES:
        return False
    connection.execute(
        "UPDATE prs SET status='closed' WHERE id=?", (pull_request_id,)
    )
    connection.execute(
        "INSERT INTO events (pr_id, revision_id, kind, body, created_at) "
        "VALUES (?, ?, 'closed', '', ?)",
        (
            pull_request_id,
            (latest_revision(connection, pull_request_id) or (None,))[0],
            utc_now(),
        ),
    )
    connection.commit()
    return True


def list_prs(connection):
    """Return all PRs as dicts with id, title, status, and created_at."""
    rows = connection.execute(
        "SELECT id, title, status, created_at FROM prs ORDER BY id"
    ).fetchall()
    return [
        {"id": row[0], "title": row[1], "status": row[2], "created_at": row[3]}
        for row in rows
    ]
