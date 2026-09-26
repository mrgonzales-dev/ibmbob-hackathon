"""bob-pr: present an agent plan as a GitHub-style pull request page.

Per-project only. All state lives in .bob-pr/bob_pr.db under the project
root, and shadow copies live in .bob-pr/tmp/<pr_id>/.

Commands:
  new       create a PR + revision 1 from a plan
  snapshot  copy planned files into the shadow dir for editing
  diff      compute real diffs of the edited copies vs the originals
  serve     run the localhost review server
  decision  print the verdict (APPROVED | CHANGES_REQUESTED | PENDING)
  revise    add a new revision after CHANGES_REQUESTED
  apply     install the approved shadow copies over the real files
  close     close a rejected or abandoned plan (terminal, read-only)
  list      print all PRs and statuses

This module is a thin facade: the implementation lives in components/ so
each concern stays easy to find and debug.
"""

from components.cli import main
from components.database import init_db
from components.decisions import get_decision, post_comment, record_decision
from components.pull_requests import close_pr, create_pr, list_prs, revise
from components.rendering import render_index_page, render_pr_page
from components.server import make_server
from components.snapshots import (
    apply_pr,
    cleanup_shadows,
    compute_diffs,
    live_diffs,
    snapshot_pr,
)

__all__ = [
    "apply_pr",
    "cleanup_shadows",
    "close_pr",
    "compute_diffs",
    "create_pr",
    "get_decision",
    "init_db",
    "list_prs",
    "live_diffs",
    "main",
    "make_server",
    "post_comment",
    "record_decision",
    "render_index_page",
    "render_pr_page",
    "revise",
    "snapshot_pr",
]

if __name__ == "__main__":
    main()
