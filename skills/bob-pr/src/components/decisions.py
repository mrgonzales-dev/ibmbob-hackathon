"""Decision handling: recording button clicks and reading verdicts.

A decision is the user's click on Approve or Request changes. Verdicts are
scoped to the latest revision, so a fresh revision starts at PENDING again.
"""

from components.pull_requests import latest_revision, utc_now

KIND_TO_VERDICT = {"approve": "APPROVED", "request_changes": "CHANGES_REQUESTED"}


def record_decision(connection, pull_request_id, kind, body):
    """Record a user click on a decision button.

    kind is 'approve' or 'request_changes'. The event is stamped with the
    latest revision id and prs.status flips to 'approved' or
    'changes_requested'.
    """
    if kind not in ("approve", "request_changes"):
        raise ValueError(f"unknown decision kind: {kind}")
    current = connection.execute(
        "SELECT status FROM prs WHERE id=?", (pull_request_id,)
    ).fetchone()
    if current and current[0] == "applied":
        return
    revision = latest_revision(connection, pull_request_id)
    revision_id = revision[0] if revision else None
    connection.execute(
        "INSERT INTO events (pr_id, revision_id, kind, body, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (pull_request_id, revision_id, kind, body or "", utc_now()),
    )
    new_status = "approved" if kind == "approve" else "changes_requested"
    connection.execute(
        "UPDATE prs SET status=? WHERE id=?", (new_status, pull_request_id)
    )
    connection.commit()


def get_decision(connection, pull_request_id):
    """Return (verdict, comments) for the latest revision of a PR.

    verdict is 'APPROVED', 'CHANGES_REQUESTED', or 'PENDING'. comments is the
    list of non-empty bodies on decision events for that revision.
    """
    revision = latest_revision(connection, pull_request_id)
    if not revision:
        return "PENDING", []
    rows = connection.execute(
        "SELECT kind, body FROM events WHERE pr_id=? AND revision_id=? "
        "AND kind IN ('approve','request_changes') ORDER BY id",
        (pull_request_id, revision[0]),
    ).fetchall()
    if not rows:
        return "PENDING", []
    verdict = KIND_TO_VERDICT[rows[-1][0]]
    comments = [body for _, body in rows if body]
    return verdict, comments
