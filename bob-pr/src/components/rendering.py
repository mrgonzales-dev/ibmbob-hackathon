"""HTML rendering: GitHub-style pages for the PR list and the PR review.

render_pr_page shows the plan summary, the timeline of events, and every
planned file with its computed diff colored like GitHub: additions green,
deletions red, context gray.
"""

import html
import json

from components.pull_requests import latest_revision, list_prs

BADGE_CLASS = {
    "open": "open",
    "approved": "approved",
    "changes_requested": "changes",
}

BADGE_LABEL = {
    "open": "Open",
    "approved": "Approved",
    "changes_requested": "Changes requested",
}

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
#banner { display: none; background: #ddf4e4; border: 1px solid #1f883d;
          border-radius: 6px; padding: 10px; margin-bottom: 12px; }
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


def render_pr_page(connection, pull_request_id):
    """Render the GitHub-style PR review page for one PR as an HTML string."""
    pull_request = connection.execute(
        "SELECT title, status FROM prs WHERE id=?", (pull_request_id,)
    ).fetchone()
    if not pull_request:
        return "<h1>PR not found</h1>"
    revision = latest_revision(connection, pull_request_id)
    file_paths = json.loads(revision[3]) if revision else []
    stored_diffs = json.loads(revision[4]) if revision and revision[4] else {}
    summary = revision[2] if revision else ""
    revision_number = revision[1] if revision else 0
    events = connection.execute(
        "SELECT kind, body, created_at FROM events WHERE pr_id=? ORDER BY id",
        (pull_request_id,),
    ).fetchall()
    timeline = "".join(
        f"<div class='card'><div class='meta'>user &middot; {html.escape(event[2])} "
        f"&middot; {html.escape(event[0])}</div>{html.escape(event[1])}</div>"
        for event in events
    )
    files_section = "".join(
        _render_file_diff(path, stored_diffs.get(path, ""))
        for path in file_paths
    )
    badge = BADGE_LABEL[pull_request[1]]
    badge_class = BADGE_CLASS[pull_request[1]]
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>PLAN-PR #{pull_request_id}</title>
<style>{PAGE_CSS}</style></head><body>
<header class="top">bob-pr &middot; PLAN-PR #{pull_request_id}</header>
<main>
<h1>{html.escape(pull_request[0])} <span class="badge {badge_class}">{badge}</span></h1>
<div id="banner">Decision recorded. Tell the agent you are done.</div>
<div class="card"><div class="meta">bob-agent opened this plan &middot; revision {revision_number}</div>
<p>{html.escape(summary)}</p></div>
{timeline}
<div class="card"><div class="meta">Files changed ({len(file_paths)}) &middot; diffs computed from shadow copies</div>
{files_section}</div>
</main>
<div class="review">
<textarea id="comment" placeholder="Leave a review comment (optional)"></textarea>
<button id="btn-approve" onclick="decide('approve')">Approve plan</button>
<button id="btn-changes" onclick="decide('request_changes')">Request changes</button>
</div>
<script>
async function decide(kind) {{
  const comment = document.getElementById('comment').value;
  const response = await fetch('/decision', {{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{pr_id: {pull_request_id}, kind, comment}})}});
  if (response.ok) {{
    document.getElementById('banner').style.display = 'block';
    document.getElementById('btn-approve').disabled = true;
    document.getElementById('btn-changes').disabled = true;
  }}
}}
</script>
</body></html>"""


def render_index_page(connection):
    """Render the PR list page, like GitHub's pull request index."""
    pull_requests = list_prs(connection)
    items = "".join(
        f"<li><a href='/pr/{pr['id']}'>#{pr['id']} {html.escape(pr['title'])}</a> "
        f"<span class='badge {BADGE_CLASS[pr['status']]}'>{pr['status']}</span></li>"
        for pr in pull_requests
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>bob-pr</title>
<style>{PAGE_CSS}</style></head><body>
<header class="top">bob-pr &middot; pull requests</header>
<main><h1>Plan PRs</h1><ul class="files">{items}</ul></main>
</body></html>"""
