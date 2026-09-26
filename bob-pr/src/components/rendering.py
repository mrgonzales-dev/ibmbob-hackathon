"""HTML rendering: GitHub-style pages for the PR list and the PR review.

render_pr_page shows the plan summary, the timeline of events, and every
planned file with its computed diff colored like GitHub: additions green,
deletions red, context gray. Icons are inline Octicons (the SVG path data
from @primer/octicons), so the pages need no network or asset files.
"""

import html
import json
import os
import re

from components.pull_requests import latest_revision, list_prs
from components.snapshots import live_diffs

# Octicon path data (viewBox 0 0 16 16).
ICONS = {
    "pr": "M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z",
    "pr-closed": "M3.25 1A2.25 2.25 0 0 1 4 5.372v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.251 2.251 0 0 1 3.25 1Zm9.5 5.5a.75.75 0 0 1 .75.75v3.378a2.251 2.251 0 1 1-1.5 0V7.25a.75.75 0 0 1 .75-.75Zm-2.03-5.273a.75.75 0 0 1 1.06 0l.97.97.97-.97a.748.748 0 0 1 1.265.332.75.75 0 0 1-.205.729l-.97.97.97.97a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018l-.97-.97-.97.97a.749.749 0 0 0 1.275-.326.749.749 0 0 1 .215-.734l.97-.97-.97-.97a.75.75 0 0 1 0-1.06ZM2.5 3.25a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0ZM3.25 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm9.5 0a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z",
    "merge": "M5.45 5.154A4.25 4.25 0 0 0 9.25 7.5h1.378a2.251 2.251 0 1 1 0 1.5H9.25A5.734 5.734 0 0 1 5 7.123v3.505a2.25 2.25 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.95-.218ZM4.25 13.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm8.5-4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM5 3.25a.75.75 0 1 0 0 .005V3.25Z",
    "check-circle": "M8 16A8 8 0 1 1 8 0a8 8 0 0 1 0 16Zm3.78-9.72a.751.751 0 0 0-.018-1.042.751.751 0 0 0-1.042-.018L6.75 9.19 5.28 7.72a.751.751 0 0 0-1.042.018.751.751 0 0 0-.018 1.042l2 2a.75.75 0 0 0 1.06 0Z",
    "x-circle": "M2.343 13.657A8 8 0 1 1 13.658 2.343 8 8 0 0 1 2.343 13.657ZM6.03 4.97a.751.751 0 0 0-1.042.018.751.751 0 0 0-.018 1.042L6.94 8 4.97 9.97a.749.749 0 0 0 .326 1.275.749.749 0 0 0 .734-.215L8 9.06l1.97 1.97a.749.749 0 0 0 1.275-.326.749.749 0 0 0-.215-.734L9.06 8l1.97-1.97a.749.749 0 0 0-.326-1.275.749.749 0 0 0-.734.215L8 6.94Z",
    "check": "M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z",
    "comment": "M1 2.75C1 1.784 1.784 1 2.75 1h10.5c.966 0 1.75.784 1.75 1.75v7.5A1.75 1.75 0 0 1 13.25 12H9.06l-2.573 2.573A1.458 1.458 0 0 1 4 13.543V12H2.75A1.75 1.75 0 0 1 1 10.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h2a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h4.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z",
    "file-diff": "M1 1.75C1 .784 1.784 0 2.75 0h7.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16H2.75A1.75 1.75 0 0 1 1 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h10.5a.25.25 0 0 0 .25-.25V4.664a.25.25 0 0 0-.073-.177l-2.914-2.914a.25.25 0 0 0-.177-.073ZM8 3.25a.75.75 0 0 1 .75.75v1.5h1.5a.75.75 0 0 1 0 1.5h-1.5v1.5a.75.75 0 0 1-1.5 0V7h-1.5a.75.75 0 0 1 0-1.5h1.5V4A.75.75 0 0 1 8 3.25Zm-3 8a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1-.75-.75Z",
    "alert": "M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575ZM8 5a.75.75 0 0 0-.75.75v2.5a.75.75 0 0 0 1.5 0v-2.5A.75.75 0 0 0 8 5Zm1 6a1 1 0 1 0-2 0 1 1 0 0 0 2 0Z",
    "chevron-left": "M9.78 12.78a.75.75 0 0 1-1.06 0L4.47 8.53a.75.75 0 0 1 0-1.06l4.25-4.25a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L6.06 8l3.72 3.72a.75.75 0 0 1 0 1.06Z",
}

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

BADGE_ICON = {
    "open": "pr",
    "approved": "check-circle",
    "changes_requested": "x-circle",
    "applied": "merge",
    "closed": "pr-closed",
}

EVENT_ACTOR = {
    "approve": "user",
    "request_changes": "user",
    "comment": "agent",
    "applied": "bob-pr",
    "closed": "bob-pr",
}

EVENT_ICON = {
    "approve": "check-circle",
    "request_changes": "x-circle",
    "comment": "comment",
    "applied": "merge",
    "closed": "pr-closed",
}

EVENT_COLOR = {
    "approve": "green",
    "request_changes": "red",
    "comment": "blue",
    "applied": "purple",
    "closed": "gray",
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
:root {
  color-scheme: dark;
  --fg: #f0f6fc; --fg-muted: #9198a1;
  --canvas: #0d1117; --canvas-subtle: #151b23;
  --border: #3d444d; --border-muted: #30363d;
  --accent: #4493f8; --accent-subtle: #121d2f;
  --success-fg: #3fb950; --success: #238636;
  --success-subtle: #12261e; --success-gutter: #033a16;
  --danger-fg: #f85149; --danger: #da3633;
  --danger-subtle: #25181b; --danger-gutter: #67060c;
  --attention-fg: #d29922; --attention-subtle: #272114;
  --attention-border: #9e6a03;
  --done: #8957e5; --done-subtle: #211830;
  --header: #010409;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
          "Liberation Mono", monospace;
}
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
       "Noto Sans", Helvetica, Arial, sans-serif;
       margin: 0; background: var(--canvas); color: var(--fg);
       font-size: 14px; line-height: 1.5; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
a:focus-visible, button:focus-visible, textarea:focus-visible {
  outline: 2px solid var(--accent); outline-offset: -1px; }
header.top { background: var(--header); color: #f0f6fc; padding: 12px 24px;
             font-size: 14px; display: flex; align-items: center; gap: 10px;
             border-bottom: 1px solid var(--border-muted); }
header.top .crumb { color: rgba(240,246,252,.7); }
header.top .sep { color: rgba(240,246,252,.4); }
header.top a { color: inherit; }
main { max-width: 1012px; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 32px; font-weight: 400; margin: 0 0 8px;
     line-height: 1.25; word-wrap: break-word; }
h1 .gh-num { color: var(--fg-muted); font-weight: 300; }
h2 { font-size: 16px; font-weight: 600; margin: 24px 0 8px; }
.subhead { display: flex; align-items: center; gap: 12px;
           padding-bottom: 16px; margin-bottom: 8px;
           border-bottom: 1px solid var(--border-muted);
           color: var(--fg-muted); }
.badge { display: inline-flex; align-items: center; gap: 6px;
         padding: 5px 12px; border-radius: 2em;
         font-size: 14px; font-weight: 500; color: #fff;
         line-height: 22px; }
.badge.sm { padding: 2px 8px; font-size: 12px; line-height: 18px; }
.badge svg { fill: currentColor; }
.badge.open, .badge.approved { background: var(--success); }
.badge.changes { background: var(--danger); }
.badge.applied { background: var(--done); }
.badge.closed { background: #6e7681; }
.card { background: var(--canvas); border: 1px solid var(--border);
        border-radius: 6px; padding: 16px; margin-bottom: 16px; }
.card .meta, .meta { color: var(--fg-muted); font-size: 12px; }
.card.warn { display: flex; gap: 10px; align-items: flex-start;
             border-color: var(--attention-border);
             background: var(--attention-subtle);
             color: var(--attention-fg); }
.card.warn svg { fill: var(--attention-fg); flex: 0 0 auto;
                 margin-top: 1px; }
/* timeline: icon discs on a rail, like GitHub events */
.tl { position: relative; margin: 16px 0; }
.tl::before { content: ""; position: absolute; left: 15px; top: 10px;
              bottom: 10px; width: 2px; background: var(--border-muted); }
.tl-item { display: flex; gap: 12px; padding: 8px 0; position: relative; }
.tl-badge { flex: 0 0 32px; width: 32px; height: 32px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            background: var(--canvas-subtle);
            border: 1px solid var(--border); color: var(--fg-muted);
            z-index: 1; }
.tl-badge svg { fill: currentColor; }
.tl-badge.green { background: var(--success); border-color: var(--success);
                  color: #fff; }
.tl-badge.red { background: var(--danger); border-color: var(--danger);
                color: #fff; }
.tl-badge.blue { background: var(--accent); border-color: var(--accent);
                 color: #fff; }
.tl-badge.purple { background: var(--done); border-color: var(--done);
                   color: #fff; }
.tl-badge.gray { background: var(--fg-muted); border-color: var(--fg-muted);
                 color: #fff; }
.tl-body { padding-top: 5px; min-width: 0; }
.tl-comment { margin-top: 6px; background: var(--canvas);
              border: 1px solid var(--border); border-radius: 6px;
              padding: 10px 12px; }
/* files changed section */
.files-head { display: flex; align-items: center; gap: 8px;
              font-size: 14px; font-weight: 600; margin: 24px 0 12px; }
.files-head svg { fill: var(--fg-muted); }
.files-head .count { color: var(--fg-muted); font-weight: 400; }
.file-diff { margin: 0 0 16px; border: 1px solid var(--border);
             border-radius: 6px; }
.file-diff .file-name { display: flex; align-items: center; gap: 8px;
                        font-family: var(--mono); font-size: 12px;
                        font-weight: 600; padding: 8px 12px;
                        background: var(--canvas-subtle);
                        border-bottom: 1px solid var(--border);
                        border-radius: 5px 5px 0 0;
                        position: sticky; top: 0; z-index: 1; }
.file-name svg { fill: var(--fg-muted); flex: 0 0 auto; }
.diffstat { margin-left: auto; display: flex; align-items: center;
            gap: 8px; font-weight: 400; }
.diffstat .add { color: var(--success-fg); }
.diffstat .del { color: var(--danger-fg); }
.diff-bar { display: flex; gap: 2px; }
.diff-bar i { width: 8px; height: 8px; border-radius: 1px;
              background: var(--border-muted); }
.diff-bar i.a { background: var(--success-fg); }
.diff-bar i.d { background: var(--danger-fg); }
.diff { overflow-x: auto; font-family: var(--mono); font-size: 12px;
        line-height: 20px; border-radius: 0 0 5px 5px; }
.diff .line { display: flex; white-space: pre; }
.line .ln { flex: 0 0 44px; padding: 0 10px 0 2px; text-align: right;
            color: var(--fg-muted); user-select: none; }
.line .code { flex: 1; padding: 0 12px 0 8px; white-space: pre; }
.diff-add { background: var(--success-subtle); }
.diff-add .ln { background: var(--success-gutter); }
.diff-del { background: var(--danger-subtle); }
.diff-del .ln { background: var(--danger-gutter); }
.diff-ctx { color: var(--fg); }
.diff-hunk { background: var(--accent-subtle); color: var(--accent); }
.diff-hunk .ln { background: var(--accent-subtle); }
.diff-meta { color: var(--fg-muted); }
/* review bar: sticky merge-box style */
.review { position: sticky; bottom: 0; background: var(--canvas);
          border-top: 1px solid var(--border); padding: 16px 0; }
.review-inner { max-width: 1012px; margin: 0 auto; padding: 0 16px; }
.review textarea { width: 100%; min-height: 72px; padding: 8px 12px;
                   border: 1px solid var(--border); border-radius: 6px;
                   font: inherit; margin-bottom: 8px; resize: vertical;
                   background: var(--canvas-subtle); }
.review textarea:focus { background: var(--canvas);
                         border-color: var(--accent);
                         box-shadow: 0 0 0 3px var(--accent-subtle);
                         outline: none; }
.review .actions { display: flex; justify-content: flex-end; gap: 8px; }
button { font: inherit; }
.btn { display: inline-flex; align-items: center; gap: 6px;
       padding: 5px 16px; font-size: 14px; font-weight: 500;
       line-height: 20px; border-radius: 6px;
       border: 1px solid rgba(31,35,40,.15); cursor: pointer;
       transition: background .15s; }
.btn svg { fill: currentColor; }
.btn-primary { background: var(--success); color: #fff; }
.btn-primary:hover { background: #2ea043; }
.btn-danger { background: var(--canvas-subtle); color: var(--danger-fg); }
.btn-danger:hover { background: var(--danger); color: #fff; }
button:disabled { opacity: .5; cursor: default; }
button:disabled:hover { background: revert; }
/* read-only state note */
.read-only { display: flex; align-items: center; gap: 10px;
             color: var(--fg-muted); }
/* toast: GitHub flash style */
#toast { position: fixed; right: 24px; bottom: 24px; z-index: 10;
         display: flex; align-items: center; gap: 10px;
         background: var(--canvas); color: var(--fg);
         padding: 12px 16px; border: 1px solid var(--border);
         border-left: 4px solid var(--success);
         border-radius: 6px; font-size: 14px; max-width: 340px;
         box-shadow: 0 8px 24px rgba(1,4,9,.85);
         opacity: 0; pointer-events: none; transform: translateY(8px);
         transition: opacity .2s, transform .2s; }
#toast.show { opacity: 1; transform: none; }
#toast svg { fill: var(--success-fg); flex: 0 0 auto; }
@media (prefers-reduced-motion: reduce) {
  #toast, .btn { transition: none; }
}
/* index list */
.box { border: 1px solid var(--border); border-radius: 6px;
       background: var(--canvas); margin-bottom: 16px; }
.box-row { display: flex; align-items: center; gap: 10px;
           padding: 8px 16px; border-top: 1px solid var(--border-muted); }
.box-row:first-child { border-top: none; }
.box-row svg { fill: var(--fg-muted); flex: 0 0 auto; }
.box-row .t { font-weight: 600; }
.box-row .n { color: var(--fg-muted); }
.box-row .end { margin-left: auto; }
"""


def _icon(name):
    """Return one inline SVG octicon by name."""
    return (
        f"<svg viewBox='0 0 16 16' width='16' height='16' "
        f"fill='currentColor' aria-hidden='true'>"
        f"<path d='{ICONS[name]}'/></svg>"
    )


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


_HUNK_RE = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _diffstat(diff_text):
    """Count additions and deletions in one unified diff."""
    adds = dels = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            adds += 1
        elif line.startswith("-"):
            dels += 1
    return adds, dels


def _diffstat_html(diff_text):
    """Render the +N/-M counts and the 5-square proportion bar."""
    adds, dels = _diffstat(diff_text)
    total = adds + dels
    if not total:
        return ""
    add_squares = round(adds / total * 5)
    del_squares = 5 - add_squares
    bar = "".join(
        f"<i class='{'a' if i < add_squares else 'd'}'></i>"
        for i in range(5)
    )
    return (
        f"<span class='diffstat'>"
        f"<span class='add'>+{adds}</span> "
        f"<span class='del'>&minus;{dels}</span>"
        f"<span class='diff-bar'>{bar}</span></span>"
    )


def _render_diff_lines(diff_text):
    """Render unified diff text as GitHub-style rows with line numbers."""
    rows = []
    old_ln = new_ln = 0
    for line in diff_text.splitlines():
        cls = _diff_line_class(line)
        if cls == "diff-meta":
            continue
        if cls == "diff-hunk":
            match = _HUNK_RE.match(line)
            if match:
                old_ln, new_ln = int(match.group(1)), int(match.group(2))
            rows.append(
                f"<div class='line diff-hunk'>"
                f"<span class='ln'></span><span class='ln'></span>"
                f"<span class='code'>{html.escape(line)}</span></div>"
            )
            continue
        if cls == "diff-add":
            old_cell, new_cell = "", new_ln
            new_ln += 1
        elif cls == "diff-del":
            old_cell, new_cell = old_ln, ""
            old_ln += 1
        else:
            old_cell, new_cell = old_ln, new_ln
            old_ln += 1
            new_ln += 1
        rows.append(
            f"<div class='line {cls}'>"
            f"<span class='ln'>{old_cell}</span>"
            f"<span class='ln'>{new_cell}</span>"
            f"<span class='code'>{html.escape(line)}</span></div>"
        )
    return "".join(rows)


def _render_file_diff(relative_path, diff_text):
    """Render one file's diff text as a GitHub-style file block."""
    body = _render_diff_lines(diff_text) or (
        "<div class='line diff-ctx'>"
        "<span class='ln'></span><span class='ln'></span>"
        "<span class='code'>no changes yet</span></div>"
    )
    return (
        f"<div class='file-diff'>"
        f"<div class='file-name'>{_icon('file-diff')}"
        f"{html.escape(relative_path)}{_diffstat_html(diff_text)}</div>"
        f"<div class='diff'>{body}</div>"
        f"</div>"
    )


def _render_event(event):
    """Render one timeline event: icon disc on the rail + meta + body."""
    kind, body, created_at = event
    actor = EVENT_ACTOR.get(kind, "user")
    icon = _icon(EVENT_ICON.get(kind, "comment"))
    color = EVENT_COLOR.get(kind, "")
    comment = (
        f"<div class='tl-comment'>{html.escape(body)}</div>" if body else ""
    )
    return (
        f"<div class='tl-item'>"
        f"<div class='tl-badge {color}'>{icon}</div>"
        f"<div class='tl-body'><div class='meta'>"
        f"{actor} &middot; {html.escape(created_at)} &middot; "
        f"{html.escape(kind)}</div>"
        f"{comment}</div></div>"
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
    timeline = "".join(_render_event(event) for event in events)
    files_section = "".join(
        _render_file_diff(path, diffs.get(path, ""))
        for path in file_paths
    )
    status = pull_request[1]
    badge = BADGE_LABEL.get(status, status)
    badge_class = BADGE_CLASS.get(status, "open")
    badge_icon = _icon(BADGE_ICON.get(status, "pr"))
    read_only_text = READ_ONLY_STATUS_TEXT.get(status)
    diffs_ready = bool(diffs)
    if read_only_text:
        review_block = (
            f"<div class='card read-only'>{_icon('alert')}"
            f"<div class='meta'>{read_only_text}</div></div>"
        )
    else:
        disabled_attr = "" if diffs_ready else " disabled"
        warning = (
            ""
            if diffs_ready
            else f"<div class='card warn'>{_icon('alert')}<div class='meta'>"
                 f"{NO_DIFFS_WARNING}</div></div>"
        )
        review_block = warning + f"""<div class="review">
<div class="review-inner">
<textarea id="comment"{disabled_attr} oninput="syncButtons()" placeholder="Type a comment to request changes, or leave empty to approve"></textarea>
<div class="actions">
<button id="btn-changes" disabled class="btn btn-danger" onclick="decide('request_changes')">{_icon('x-circle')}Request changes</button>
<button id="btn-approve"{disabled_attr} class="btn btn-primary" onclick="decide('approve')">{_icon('check')}Approve plan</button>
</div>
</div>
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
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PLAN-PR #{pull_request_id}</title>
<style>{PAGE_CSS}</style></head><body>
<header class="top"><strong>bob-pr</strong>
<span class="sep">/</span>
<a class="crumb" href="/">pull requests</a>
<span class="sep">/</span>
<span class="crumb">#{pull_request_id}</span></header>
<main>
<h1>{html.escape(pull_request[0])} <span class="gh-num">#{pull_request_id}</span></h1>
<div class="subhead">
<span class="badge {badge_class}">{badge_icon}{badge}</span>
<span>bob-agent opened this plan &middot; revision {revision_number}</span>
</div>
<div class="card"><p>{html.escape(summary)}</p></div>
{timeline}
<div class="files-head">{_icon('file-diff')}Files changed
<span class="count">({len(file_paths)}) &middot; diffs computed from shadow copies</span></div>
{files_section}
</main>
{review_block}
<div id="toast"></div>
<script>
(function() {{
  const toast = document.getElementById('toast');
  const hash = location.hash.slice(1);
  const CHECK = '{_icon("check-circle")}';
  const COMMENT = '{_icon("comment")}';
  if (hash === 'approve') {{
    toast.innerHTML = CHECK + '<span>Approved — tell your agent you approved this</span>';
  }} else if (hash === 'request_changes') {{
    toast.innerHTML = COMMENT + '<span>Changes requested — tell your agent you asked for changes</span>';
  }} else {{
    return;
  }}
  toast.classList.add('show');
}})();
</script>
</body></html>"""


def _pr_list_items(pull_requests):
    """Render a list of PR rows as linked items with status badges."""
    rows = []
    for pr in pull_requests:
        status = pr["status"]
        icon = _icon(BADGE_ICON.get(status, "pr"))
        badge = (
            f"<span class='badge sm {BADGE_CLASS.get(status, 'open')}'>"
            f"{icon}{html.escape(status)}</span>"
        )
        rows.append(
            f"<div class='box-row'>{icon}"
            f"<a class='t' href='/pr/{pr['id']}'>"
            f"{html.escape(pr['title'])}</a>"
            f"<span class='n'>#{pr['id']}</span>"
            f"<span class='end'>{badge}</span></div>"
        )
    return "".join(rows)


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
        f"<h2>Closed</h2><div class='box'>{_pr_list_items(closed_prs)}</div>"
        if closed_prs
        else ""
    )
    applied_section = (
        f"<h2>Applied (audit)</h2><div class='box'>{_pr_list_items(applied_prs)}</div>"
        if applied_prs
        else ""
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bob-pr</title>
<style>{PAGE_CSS}</style></head><body>
<header class="top"><strong>bob-pr</strong>
<span class="sep">/</span>
<span class="crumb">pull requests</span></header>
<main><h1>Plan PRs</h1>
<h2>Open</h2><div class="box">{_pr_list_items(open_prs)}</div>
{closed_section}
{applied_section}
</main>
</body></html>"""
