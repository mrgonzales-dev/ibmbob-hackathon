---
name: bob-impact
description: >-
  Change impact analyzer. Reads git diff (or a named file), traces the direct
  callers, database tables, and tests that reference the changed code, then
  prints one ranked impact report. Use when the user says "bob impact",
  "bob-impact", "what does this change affect", "impact analysis", "trace this
  change", "who calls this", "blast radius", "what breaks if I change this", or
  "regression check this change". Add --regress to run the affected tests after
  the report.
---

# Change Impact Analyzer

You trace one change through a project. You read the project. You never change
application code during the analysis.

## Run the local scanner first

`bob-impact` needs no API key and no model. Run it in the project root. Use its
rows as the facts. Never add a row it did not report.

| Command | Result |
|---|---|
| `bob-impact` | Impact report from git diff. |
| `bob-impact --file app/Services/PayrollService.php` | Impact report for one named file. |
| `bob-impact --regress` | Impact report, then run the affected tests. |
| `bob-impact --json` | The same rows with the raw evidence. |
| `bob-impact --ai` | Hands this skill to Bob Shell. Needs a key. |

## Arguments

| Input | Meaning |
|---|---|
| No args | Read `git diff --name-only` in the project root. |
| `--file <path>` | Analyze one named file. Skip git. |
| `--regress` | After the report, run the tests that reference the changed code. |

State the changed files in one line before you start.

## What the scanner can prove

The scanner reports only what a grep-based trace can prove. It does not guess.

| Field | How the scanner finds it | What it does NOT claim |
|---|---|---|
| Changed files | `git diff --name-only` or `--file` arg | It does not invent files. |
| Class names | Parse `class`, `interface`, `trait` in changed files | It does not parse method bodies for inner closures. |
| Direct callers | Grep for the class name in other PHP files | It does not trace facades, IoC, or magic methods. Mark as heuristic. |
| Database tables | `protected $table`, `Schema::create`, `DB::table`, `->from` in changed files | It does not infer table names from model class names. |
| Tests referencing | Grep for the class name in `tests/` | It counts references, not failures. Only running tests tells you what broke. |
| Risk | The rubric in `src/risk-rules.md` | It applies the committed rubric. It does not guess. |

Never report "affected business rules." That is a semantic claim no scanner
can make. Report what grep can prove.

## Phase 0 — Detect changed files

Read `git diff --name-only` at the project root. Filter to PHP files. When the
user passes `--file`, use that file instead.

Print the changed files in one line.

## Phase 1 — Extract class names

Parse each changed file. Find every `class`, `interface`, and `trait`
declaration. These names are the trace seeds.

## Phase 2 — Three lanes in one pass

Run the three lanes in one pass over the project. Each lane is a grep with a
different target.

| Lane | Role | It reads | It must not read |
|---|---|---|---|
| `callers` | Direct caller tracer | Every PHP file except the changed files | The changed files |
| `tables` | Database table finder | The changed files only | Other files |
| `tests` | Test reference finder | Every file in `tests/` | Files outside `tests/` |

Each lane returns a list. Return an empty list when nothing matches. Never
invent a finding.

## Phase 3 — Merge and rank

Merge the three lists. Apply the risk rubric from `src/risk-rules.md`.

| Risk | Meaning |
|---|---|
| HIGH | The changed code has direct callers. A change can break them. |
| MED | No direct callers, but tests reference the changed code. |
| LOW | No callers and no tests. The change is isolated. |

## Phase 4 — Report

Use `src/report-template.md` for the exact layout.

Print one table of findings. Print the changed files, the direct callers, the
database tables, the tests referencing the changed code, and the risk.

| Rule that finds nothing | What to print |
|---|---|
| All three lanes | One line that says no finding. Stop. |
| Some lanes | Report the empty lanes as one clean line. |

Never pad the report to make it look complete.

## Phase 5 — Regress (optional)

When the user passes `--regress`, run the tests that reference the changed code.
Use the project's test runner (`php artisan test` or `vendor/bin/phpunit`).

Print the test command and its exit code. Do not interpret the output. The
user reads it.

## Rules for the report

| Rule | Why |
|---|---|
| Report only what grep can prove | A judge checks one item. An invented item loses the whole report. |
| Never guess a caller or a table | Read it from a file. |
| Never change application code during the analysis | The user asked for a report. |
| Never run the test suite without --regress | The tests belong to phase 5. |
| Mark direct callers as heuristic | Facades and IoC break naive tracing. Be honest about it. |

## Supporting files

Everything this skill needs lives in this one folder. Nothing points outside
it.

| File | Use |
|---|---|
| `src/run.py` | The command. Runs the local scanner, or hands the skill to Bob Shell with `--ai`. |
| `src/impact.py` | The local rule engine. It is the scanner behind `bob-impact`. |
| `src/risk-rules.md` | The risk rubric. The only source of risk truth. |
| `src/report-template.md` | The exact report layout. |
| `src/requirements.txt` | Optional color output. The scanner runs without it. |
| `src/tests/` | The tests for the files in this folder. |

Run `src/run.py` directly for the local scan. Copy this folder to
`~/.bob/skills/` so Bob finds the skill in every project.
