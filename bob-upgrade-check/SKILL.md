---
name: bob-upgrade-check
description: >-
  Major framework upgrade risk analyzer. Scans a PHP project for the package,
  code, and config changes that a version bump causes, then returns one ranked
  HIGH/MED/LOW report and an optional phased plan. Use when the user says "bob
  upgrade", "bob-upgrade-check", "upgrade laravel", "upgrade to Laravel 12", "bump
  laravel", "analyze this upgrade", "upgrade risk", "what breaks in this
  upgrade", "is it safe to upgrade", or "check what breaks when I upgrade", and
  also when the user asks to plan a major version bump for a Composer project.
---

# Dependency Upgrade Risk Analyzer

You analyze one project against one target version. You read the project. You
never change application code during the analysis.

## Run the local scanner first

`bob-upgrade-check` needs no API key and no model. Run it in the project root. Use
its rows as the facts. Never add a row it did not report.

| Command | Result |
|---|---|
| `bob-upgrade-check` | Ranked findings as a text table. |
| `bob-upgrade-check --json` | The same rows with the raw evidence. |
| `bob-upgrade-check --ai` | Hands this skill to Bob Shell. Needs a key. |

The scanner already runs the three lanes below. Add your own reading only where
the report points at a file you must judge.

## Arguments

| Input | Meaning |
|---|---|
| A package and a version | The user named the target. Use it. |
| A package and no version | Use the next major version of that package. |
| Nothing | Read the project, find the framework, and use its next major version. |

State the target you chose in one line before you start. If the user named a
target, do not change it.

## Phase 0 — Detect

Read `composer.json` at the project root. Find the framework package and its
installed version in `composer.lock`.

Print the current version and the target version.

## Phase 1 — Inventory

Run the preflight script. It counts files, packages, and tests. Its output is
exact. Do not count anything yourself.

```shell
python bob-upgrade-check/src/preflight.py --root . --format json
```

On Windows, use `py -3` in place of `python` when `python` is not on the PATH.
When the script is missing, count with the search tool instead. Say that you
counted by hand.

## Phase 2 — Three lanes in parallel

Run the three lanes in one turn so they read the project at the same time. Use
the `explore` subagent type. It is read-only.

Each lane has one role. Keep the roles apart so each lane stays small.

| Lane | Role | It reads | It must not read |
|---|---|---|---|
| `deps` | Package auditor | `composer.json`, `composer.lock` | Application code, `config/` |
| `apis` | Source auditor | Every PHP file | `composer.json` |
| `config` | Configuration auditor | `config/`, the code that reads disks | `composer.lock` |

Read `src/laravel-12-breaking-changes.md` first. Work only from its tables.
That file is the whole truth for every lane.

Each lane returns a list. Return an empty list when nothing matches. Never
invent a finding. Never report a problem the guide does not mention.

## Phase 3 — Merge and rank

Merge the three lists. Sort by severity, then by file path.

| Severity | Meaning |
|---|---|
| HIGH | The upgrade breaks at runtime, or the build stops. |
| MED | The upgrade changes behavior in a way the code must answer. |
| LOW | The upgrade changes a default or a return shape. |

Drop every duplicate. Keep the highest severity for each rule and file.

## Phase 4 — Report

Use `src/report-template.md` for the exact layout.

Print one table of findings. Print the source URL once, at the end.

| Rule that finds nothing | What to print |
|---|---|
| All three lanes | One line that says no finding. Stop. |
| Some lanes | Report the empty lanes as one clean line. |

Never pad the report to make it look complete.

## Phase 5 — Confirm, then plan

Ask the user before you write any plan. Do not write files during the analysis.

When the user wants a plan, order the work by severity. Put the HIGH items
first. The global Laravel installer sits outside the project, so list
`composer global update laravel/installer` as a manual step, never as a finding.

Write `UPGRADE-PR.md` only when the user asks for it. Run `gh pr create` only
when the `gh` command exists and the repository has a remote.

## Rules for the report

| Rule | Why |
|---|---|
| Report only what the rule file or the live guide states | A judge checks one item. An invented item loses the whole report. |
| Never guess a version or a package constraint | Read it from a file. |
| Never change application code during the analysis | The user asked for a report. |
| Never run the test suite during the analysis | The tests belong to phase 5. |
| Keep the three lanes separate | A separate context per lane keeps the main thread small. |

## Supporting files

Everything this skill needs lives in this one folder. Nothing points outside
it.

| File | Use |
|---|---|
| `src/run.py` | The command. Runs the local scanner, or hands the skill to Bob Shell with `--ai`. |
| `src/laravel12.py` | The local rule engine. It is the scanner behind `bob-upgrade-check`. |
| `src/laravel-12-breaking-changes.md` | The only source of breaking-change truth. |
| `src/report-template.md` | The exact report layout. |
| `src/preflight.py` | Counts files, packages, and tests. |
| `src/requirements.txt` | Optional color output. The scanner runs without it. |
| `src/tests/` | The tests for the files in this folder. |

Run `src/run.py` directly for the local scan. Copy this folder to
`~/.bob/skills/` so Bob finds the skill in every project.
