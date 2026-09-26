"""HTML rendering: GitHub-style pages for the PR list and the PR review.

render_pr_page shows the plan summary, the timeline of events, and every
planned file with its computed diff colored like GitHub: additions green,
deletions red, context gray.
"""

import html
import json
import os

from components.pull_requests import latest_revision, list_prs
from components.snapshots import live_diffs

BADGE_CLASS = {
    "open": "open",
    "approved": "approved",
    "changes_requested": "changes",
    "applied": "applied",
    "closed": "closed",
}

BADGE_LABEL = {
    "open": "Open",
    "approved": "Approved",
    "changes_requested": "Changes requested",
    "applied": "Applied",
    "closed": "Closed",
}

EVENT_ACTOR = {
    "approve": "user",
    "request_changes": "user",
    "comment": "agent",
    "applied": "bob-pr",
    "closed": "bob-pr",
}

READ_ONLY_STATUS_TEXT = {
    "approved": "This PR is approved — approval is final and cannot be "
    "changed. Tell your agent to apply the plan.",
    "applied": "This PR is applied — read-only audit snapshot. "
    "No actions available.",
    "closed": "This PR is closed — the plan was not applied. "
    "No actions available.",
}

NO_DIFFS_WARNING = (
    "No diffs computed for this revision — the agent must snapshot and "
    "run the diff command before you can decide."
)

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
.badge.applied { background: #8250df; color: #fff; }
.badge.closed { background: #59636e; color: #fff; }
.card { background: #fff; border: 1px solid #d1d9e0; border-radius: 8px;
        padding: 16px; margin-bottom: 16px; }
.card .meta { color: #59636e; font-size: 13px; margin-bottom: 8px; }
.files li { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 13px; margin: 4px 0; }
.file-diff { margin: 12px 0; }
.file-diff .file-name { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                        font-size: 13px; font-weight: 600; padding: 6px 10px;
                        background: #f6f8fa; border: 1px solid #d1d9e0;
                        border-bottom: none; border-radius: 6px 6px 0 0; }
.diff { border: 1px solid #d1d9e0; border-radius: 0 0 6px 6px;
        overflow-x: auto; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 12px; }
.diff .line { padding: 0 10px; white-space: pre; line-height: 1.5; }
.diff-add { background: #dafbe1; }
.diff-del { background: #ffebe9; }
.diff-ctx { color: #59636e; }
.diff-hunk { background: #ddf4ff; color: #0969da; }
.diff-meta { color: #59636e; }
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
.card.warn { border-color: #d4a72c; background: #fff8e6; }
#toast { position: fixed; right: 20px; bottom: 20px; z-index: 10;
         background: #1f2328; color: #fff; padding: 12px 18px;
         border-radius: 8px; font-size: 14px; max-width: 320px;
         box-shadow: 0 4px 12px rgba(0,0,0,.25);
         opacity: 0; pointer-events: none; transition: opacity .3s; }
#toast.show { opacity: 1; }
a { color: #0969da; text-decoration: none; }
"""


def _diff_line_class(line):
    """Map one diff line to its CSS class by its leading character."""
    if line.startswith(("+++", "---")):
        return "diff-meta"
    if line.startswith("@@"):
        return "diff-hunk"
    if line.startswith("+"):
        return "diff-add"
    if line.startswith("-"):
        return "diff-del"
    return "diff-ctx"


def _render_file_diff(relative_path, diff_text):
    """Render one file's diff text as colored HTML lines."""
    escaped_lines = "".join(
        f"<div class='line {_diff_line_class(line)}'>{html.escape(line)}</div>"
        for line in diff_text.splitlines()
    )
    return (
        f"<div class='file-diff'>"
        f"<div class='file-name'>{html.escape(relative_path)}</div>"
        f"<div class='diff'>{escaped_lines or '<div class=\"line diff-ctx\">no changes yet</div>'}</div>"
        f"</div>"
    )


def render_pr_page(connection, pull_request_id, project_root=None):
    """Render the GitHub-style PR review page for one PR as an HTML string.

    When project_root is given and the shadow dir still exists, diffs are
    computed live from the shadow copies — the page always shows the
    current edits, not the last stored diff. Without shadow copies the
    stored diffs render; apply_pr refreshes them at apply time as the
    audit record.
    """
    pull_request = connection.execute(
        "SELECT title, status FROM prs WHERE id=?", (pull_request_id,)
    ).fetchone()
    if not pull_request:
        return "<h1>PR not found</h1>"
    revision = latest_revision(connection, pull_request_id)
    file_paths = json.loads(revision[3]) if revision else []
    summary = revision[2] if revision else ""
    revision_number = revision[1] if revision else 0
    shadow_dir = os.path.join(
        project_root or "", ".bob-pr", "tmp", str(pull_request_id)
    )
    if project_root is not None and os.path.isdir(shadow_dir):
        diffs = live_diffs(project_root, pull_request_id, file_paths)
    else:
        diffs = (
            json.loads(revision[4]) if revision and revision[4] else {}
        )
    events = connection.execute(
        "SELECT kind, body, created_at FROM events WHERE pr_id=? ORDER BY id",
        (pull_request_id,),
    ).fetchall()
    timeline = "".join(
        f"<div class='card'><div class='meta'>"
        f"{EVENT_ACTOR.get(event[0], 'user')} &middot; "
        f"{html.escape(event[2])} &middot; {html.escape(event[0])}</div>"
        f"{html.escape(event[1])}</div>"
        for event in events
    )
    files_section = "".join(
        _render_file_diff(path, diffs.get(path, ""))
        for path in file_paths
    )
    status = pull_request[1]
    badge = BADGE_LABEL.get(status, status)
    badge_class = BADGE_CLASS.get(status, "open")
    read_only_text = READ_ONLY_STATUS_TEXT.get(status)
    diffs_ready = bool(diffs)
    if read_only_text:
        review_block = (
            f"<div class='card'><div class='meta'>{read_only_text}</div></div>"
        )
    else:
        disabled_attr = "" if diffs_ready else " disabled"
        warning = (
            ""
            if diffs_ready
            else f"<div class='card warn'><div class='meta'>"
                 f"{NO_DIFFS_WARNING}</div></div>"
        )
        review_block = warning + f"""<div class="review">
<textarea id="comment"{disabled_attr} oninput="syncButtons()" placeholder="Type a comment to request changes, or leave empty to approve"></textarea>
<button id="btn-approve"{disabled_attr} onclick="decide('approve')">Approve plan</button>
<button id="btn-changes" disabled onclick="decide('request_changes')">Request changes</button>
</div>
<script>
const DIFFS_READY = {str(diffs_ready).lower()};
function syncButtons() {{
  if (!DIFFS_READY) return;
  const hasComment = document.getElementById('comment').value.trim() !== '';
  document.getElementById('btn-approve').disabled = hasComment;
  document.getElementById('btn-changes').disabled = !hasComment;
}}
async function decide(kind) {{
  if (!DIFFS_READY) return;
  const comment = document.getElementById('comment').value;
  const response = await fetch('/decision', {{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{pr_id: {pull_request_id}, kind, comment}})}});
  if (response.ok) {{
    location.href = "/pr/{pull_request_id}#" + kind;
  }}
}}
</script>"""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>PLAN-PR #{pull_request_id}</title>
<style>{PAGE_CSS}</style></head><body>
<header class="top">bob-pr &middot; PLAN-PR #{pull_request_id}</header>
<main>
<p><a href="/">&larr; All pull requests</a></p>
<h1>{html.escape(pull_request[0])} <span class="badge {badge_class}">{badge}</span></h1>
<div class="card"><div class="meta">bob-agent opened this plan &middot; revision {revision_number}</div>
<p>{html.escape(summary)}</p></div>
{timeline}
<div class="card"><div class="meta">Files changed ({len(file_paths)}) &middot; diffs computed from shadow copies</div>
{files_section}</div>
</main>
{review_block}
<div id="toast"></div>
<script>
(function() {{
  const toast = document.getElementById('toast');
  const hash = location.hash.slice(1);
  if (hash === 'approve') {{
    toast.textContent = 'Approved — tell your agent you approved this';
  }} else if (hash === 'request_changes') {{
    toast.textContent = 'Changes requested — tell your agent you asked for changes';
  }} else {{
    return;
  }}
  toast.classList.add('show');
}})();
</script>
</body></html>"""


def _pr_list_items(pull_requests):
    """Render a list of PR rows as linked items with status badges."""
    return "".join(
        f"<li><a href='/pr/{pr['id']}'>#{pr['id']} {html.escape(pr['title'])}</a> "
        f"<span class='badge {BADGE_CLASS.get(pr['status'], 'open')}'>"
        f"{html.escape(pr['status'])}</span></li>"
        for pr in pull_requests
    )


def render_index_page(connection):
    """Render the PR list page with Open, Closed, and Applied (audit)
    sections, like GitHub's pull request index. The terminal sections
    only render when they hold a PR."""
    pull_requests = list_prs(connection)
    open_prs = [
        p for p in pull_requests if p["status"] not in ("applied", "closed")
    ]
    closed_prs = [p for p in pull_requests if p["status"] == "closed"]
    applied_prs = [p for p in pull_requests if p["status"] == "applied"]
    closed_section = (
        f"<h2>Closed</h2><ul class='files'>{_pr_list_items(closed_prs)}</ul>"
        if closed_prs
        else ""
    )
    applied_section = (
        f"<h2>Applied (audit)</h2><ul class='files'>{_pr_list_items(applied_prs)}</ul>"
        if applied_prs
        else ""
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>bob-pr</title>
<style>{PAGE_CSS}</style></head><body>
<header class="top">bob-pr &middot; pull requests</header>
<main><h1>Plan PRs</h1>
<h2>Open</h2><ul class="files">{_pr_list_items(open_prs)}</ul>
{closed_section}
{applied_section}
</main>
</body></html>"""
