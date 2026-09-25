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
python3 SKILL_DIR/src/bob_pr.py serve            # localhost server, prints the URL
python3 SKILL_DIR/src/bob_pr.py decision <id>    # APPROVED | CHANGES_REQUESTED | PENDING + comments
python3 SKILL_DIR/src/bob_pr.py revise <id> --summary "..." --files f1.py
python3 SKILL_DIR/src/bob_pr.py list             # all PRs and statuses
```

## Flow

1. Finish the plan. Do NOT write implementation code yet.
2. Run `new` to record the plan as PR revision 1.
3. Run `serve` in the background. Tell the user the URL and to open it in the IDE's built-in Simple Browser or a normal browser.
4. End the turn. Wait for the user to say they reviewed it — do not poll.
5. Run `decision <id>` and act on the verdict:
   - `APPROVED` — implement exactly what the PR describes, nothing more.
   - `CHANGES_REQUESTED` — read the comment, run `revise`, go to step 3.
   - `PENDING` — tell the user no decision was clicked yet.

## Rules

- Never implement before `decision` returns `APPROVED`.
- Each `revise` creates a new revision of the same PR — never a new PR for the same plan.
- `.bob-pr/` is a generated artifact. Never commit it.
