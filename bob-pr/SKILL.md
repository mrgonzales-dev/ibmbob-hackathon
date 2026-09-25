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
python3 SKILL_DIR/src/bob_pr.py snapshot <id>    # copy planned files to .bob-pr/tmp/<id>/
python3 SKILL_DIR/src/bob_pr.py diff <id>        # compute real diffs after you edit the copies
python3 SKILL_DIR/src/bob_pr.py serve            # localhost server, prints the URL
python3 SKILL_DIR/src/bob_pr.py decision <id>    # APPROVED | CHANGES_REQUESTED | PENDING + comments
python3 SKILL_DIR/src/bob_pr.py revise <id> --summary "..." --files f1.py
python3 SKILL_DIR/src/bob_pr.py apply <id>       # install approved copies over the real files
python3 SKILL_DIR/src/bob_pr.py list             # all PRs and statuses
```

## Flow

1. Finish the plan. Do NOT write implementation code yet.
2. Run `new` to record the plan as PR revision 1.
3. Run `snapshot` — it copies each planned file into `.bob-pr/tmp/<id>/` and fingerprints the originals.
4. Make the planned edits **on the shadow copies** under `.bob-pr/tmp/<id>/`, exactly as you would on real files.
5. Run `diff` — real unified diffs are computed and attached to the revision.
6. Run `serve` in the background. Tell the user the URL and to open it in the IDE's built-in Simple Browser or a normal browser.
7. End the turn. Wait for the user to say they reviewed it — do not poll.
8. Run `decision <id>` and act on the verdict:
   - `APPROVED` — run `apply <id>` to install the shadow copies onto the real files, then finish any work the plan did not cover.
   - `CHANGES_REQUESTED` — read the comment, edit the same shadow copies, run `revise` with the updated plan, run `diff`, go to step 6.
   - `PENDING` — tell the user no decision was clicked yet.

## Rules

- Never edit real project files before `decision` returns `APPROVED` and `apply` runs. Edit only `.bob-pr/tmp/<id>/` copies.
- If `apply` reports `STALE` for a file, the user changed it during review — do not overwrite it; tell the user and re-plan that file.
- Each `revise` creates a new revision of the same PR — never a new PR for the same plan.
- `.bob-pr/` (database and shadow copies) is a generated artifact. Never commit it.
