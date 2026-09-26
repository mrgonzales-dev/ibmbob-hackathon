---
name: bob-pr
description: >-
  Present a plan as a GitHub-style pull request page the user approves before coding starts.
  Use when the user says "present as a PR", "show me the plan PR", "PR the plan", or when a plan needs an explicit approve/request-changes gate before implementation.
---

# bob-pr

Turn a plan into a reviewable pull-request page served on localhost. Per-project only: all state lives in `.bob-pr/` under the project root. Never store state globally.

## Commands

Run from the project root. `SKILL_DIR` is this skill's directory.

```
python3 SKILL_DIR/src/bob_pr.py new --title "..." --summary "..." --files f1.py,f2.py
python3 SKILL_DIR/src/bob_pr.py snapshot <id>    # copy planned files to .bob-pr/tmp/<id>/ (keeps edited copies, warns)
python3 SKILL_DIR/src/bob_pr.py diff <id>        # compute real diffs after you edit the copies
python3 SKILL_DIR/src/bob_pr.py serve            # detached background server, prints the URL (returns immediately)
python3 SKILL_DIR/src/bob_pr.py stop             # stop the background review server
python3 SKILL_DIR/src/bob_pr.py decision <id>    # APPROVED | CHANGES_REQUESTED | PENDING | UNKNOWN + comments
python3 SKILL_DIR/src/bob_pr.py revise <id> --summary "..." --files f1.py  # --files optional: inherits previous revision's list
python3 SKILL_DIR/src/bob_pr.py apply <id>       # install approved copies over the real files
python3 SKILL_DIR/src/bob_pr.py close <id>       # close a rejected plan; deletes its shadow copies
python3 SKILL_DIR/src/bob_pr.py comment <id> --body "..."  # post a note on the PR timeline
python3 SKILL_DIR/src/bob_pr.py list             # all PRs and statuses
```

## Flow

1. Finish the plan. Do NOT write implementation code yet.
2. Run `new` to record the plan as PR revision 1.
3. Run `snapshot` — it copies each planned file into `.bob-pr/tmp/<id>/` and fingerprints the originals.
4. Make the planned edits **on the shadow copies** under `.bob-pr/tmp/<id>/`, exactly as you would on real files.
5. Run `diff` — real unified diffs are computed and attached to the revision. The page always diffs live shadow copies, so later edits show without re-running it.
6. Run `serve` — it detaches a background server and returns immediately with the URL. Tell the user to open it in the IDE's built-in Simple Browser or a normal browser. Run `stop` when review is done.
7. End the turn. Wait for the user to say they reviewed it — do not poll.
8. Run `decision <id>` and act on the verdict:
   - `APPROVED` — run `apply <id>` to install the shadow copies onto the real files, then finish any work the plan did not cover.
   - `CHANGES_REQUESTED` — read the comment, edit the same shadow copies, run `revise` with the updated plan, run `diff`, go to step 6.
   - `PENDING` — tell the user no decision was clicked yet.
   - `UNKNOWN` — the id is wrong; run `list` to find the right PR.

## Rules

- Never edit real project files before `decision` returns `APPROVED` and `apply` runs. Edit only `.bob-pr/tmp/<id>/` copies.
- The page disables the decision buttons until diffs exist. If the user says the buttons are greyed out, run `snapshot` then `diff`.
- Always pass `--files` to `new`. For `revise`, `--files` is optional — the previous revision's list is inherited.
- Once approved, a PR is locked — further clicks are ignored and the buttons disappear. `APPROVED` only ends when you run `apply` (status `applied`) or `close`.
- If `apply` reports `STALE` for a file, the user changed it during review — do not overwrite it; tell the user and re-plan that file.
- If `apply` reports `MISSING` for a file, its shadow copy was never written — write it, then run `apply` again.
- If the user abandons the plan, run `close <id>` — closed and applied PRs are terminal: they refuse `revise`, `decision`, `apply`, and `close`.
- Each `revise` creates a new revision of the same PR — never a new PR for the same plan.
- Use `comment` to leave notes on the timeline (e.g., "waiting on CI"). Comments never move the verdict.
- `.bob-pr/` (database and shadow copies) is a generated artifact. Never commit it.
