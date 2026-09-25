# Upgrade Risk Analyzer — Plan

## Overview

**Goal:** Build a Bob skill (`bob-upgrade`) that analyzes a Laravel 11 project
for risks before an upgrade to Laravel 12. Bob uses parallel subagents to scan
dependencies, PHP code, and config files. Bob then produces a risk report and
an optional phased upgrade plan.

**Scope:** Laravel 11 to 12 only. One Python script, and only for counting.

**Invocation:** `bob-upgrade [package] [version]`. The wrapper calls
`bob run`. Inside a Bob Shell session the same skill runs as `/bob-upgrade`.

**Target sample app:** `sample-app/`, a Laravel 11 stub with planted breakage
that matches the official upgrade guide.

**Source of truth:** <https://laravel.com/docs/12.x/upgrade>. Every breaking
change lives in `.bob/skills/bob-upgrade/src/laravel-12-breaking-changes.md`.
No breaking change is ever written from memory.

---

## Sub-Task 1 — Create the skill scaffold

**Status:** [x] done

### Intent
Create the directory and `SKILL.md` file for the `bob-upgrade` skill. This
gives Bob a trigger and a place to load instructions from.

### Expected Outcomes
- Directory `.bob/skills/bob-upgrade/` exists.
- File `.bob/skills/bob-upgrade/SKILL.md` exists with valid frontmatter.
- The skill activates on `bob upgrade`, `/bob-upgrade`, or `upgrade laravel`.

### Todo List
1. [x] Create `.bob/skills/bob-upgrade/` directory.
2. [x] Write `SKILL.md` with `name` and a trigger-rich `description`.

### Relevant Context
- Bob Shell reads `.bob/skills/`, not `.opencode/skills/`.
- `.opencode/` is in `.gitignore`, so a skill there would never ship.
- The skill directory name equals the `name` field in the frontmatter.

---

## Sub-Task 2 — Write the verified breaking-change data file

**Status:** [x] done

### Intent
Write the only source of breaking-change truth. The skill reads it. The
auditors quote it. The synthesizer validates findings against it.

### Expected Outcomes
- File `src/laravel-12-breaking-changes.md` exists.
- Every row carries the impact rating that Laravel publishes.
- Every row carries a detect signal that a search tool can match.
- A closing table lists the claims that the guide does not support.

### Todo List
1. [x] Map each impact rating to a report severity.
2. [x] Add the dependency rows DEP-001 to DEP-004.
3. [x] Add the model, request, validation, storage, container, and database rows.
4. [x] Add a remediation section with before and after code.
5. [x] Add the table of unsupported claims.

### Relevant Context
- The guide lists three High impact changes: `laravel/framework` to `^12.0`,
  `phpunit/phpunit` to `^11.0`, and `pestphp/pest` to `^3.0`.
- The one Medium impact change is the UUIDv7 identifier change.
- Carbon 2 support removal is Low impact, not High.

---

## Sub-Task 3 — Write the preflight counter

**Status:** [x] done

### Intent
Count PHP files, packages, and test cases exactly. Counting is deterministic
work, so a script does it. The agent keeps the judgment work.

### Expected Outcomes
- File `src/preflight.py` exists and uses only the Python standard library.
- `--format json` prints machine-readable counts for the agent.
- `--format text` prints the box-drawing inventory header.
- Exit `0` on success, `1` when no `composer.json` exists, `2` on bad input.

### Todo List
1. [x] Write `src/tests/test_preflight.py` first.
2. [x] Get user approval for the test code.
3. [x] Write `src/preflight.py` until the tests pass.
4. [x] Run the tests only after the user says so.

### Relevant Context
- Python 3.13 is installed. `pytest` is absent, so the tests use `unittest`.
- The tests cover each function on its own, so coverage maps one to one.
- The report template reads the counts from this script.
- 39 tests pass in 0.8 seconds.
- The Windows console uses cp1252, which cannot encode the box characters.
  The script forces UTF-8 output so the header never crashes the run.

---

## Sub-Task 4 — Write the report template

**Status:** [x] done

### Intent
Define the exact terminal output. A judge reads the screen, not the code.

### Expected Outcomes
- File `src/report-template.md` exists.
- The header uses the BOB THE BUILDER box.
- The severity summary shows HIGH, MED, and LOW counts.
- Each HIGH finding shows file, line, uses, replacement, and rule ID.
- The confirmation prompt ends the report.

### Relevant Context
- Never print a finding that has no file.
- Print no severity summary when there are no findings. Print a clean result.
- The report must stop and wait after the confirmation prompt.

---

## Sub-Task 5 — Write the four personas

**Status:** [x] done

### Intent
Give each lane a role, a tool ceiling, and a fixed output shape. Read-only
personas stop an auditor from editing the project by accident.

### Expected Outcomes
- Files `.bob/agents/dep-auditor.md`, `api-auditor.md`, `config-auditor.md`,
  and `compat-synthesizer.md` exist.
- Each persona sets `tools: [read]`.
- Each persona returns findings in the same shape.

### Relevant Context
- Spawn the three auditors in one turn so they run in parallel.
- Use the `explore` subagent type. It works in Agent mode and in Plan mode.
- The synthesizer adds no finding of its own. It only ranks and validates.

---

## Sub-Task 6 — Write the skill instructions

**Status:** [x] done

### Intent
Write the six phases. Detect, audit, synthesize, report, confirm, plan.

### Expected Outcomes
- `SKILL.md` covers all five phases and the argument rules.
- The skill states the target version before it starts.
- The skill runs the preflight script before the report.
- The skill never changes code during the analysis.

### Relevant Context
- The name is `bob-upgrade`. The file `bob` would break Bob Shell itself.
- Bare `bob-upgrade` means auto-detect the framework and use the next major.
- Phase 6 writes `UPGRADE-PR.md`, then offers `gh pr create`.

---

## Sub-Task 7 — Create the sample app

**Status:** [x] done

### Intent
Create a demo target with planted breakage that matches the real upgrade guide.

### Expected Outcomes
- Directory `sample-app/` exists with 18 PHP files.
- `composer.json` carries three High impact breaks and Carbon 2.
- `app/Models/User.php` uses the removed `HasVersion7Uuids` trait.
- `app/Http/Controllers/UserController.php` uses the `image` rule and a
  dotted `mergeIfMissing` key.
- `app/Services/PayrollService.php` calls `Storage::disk('local')` and
  `Concurrency::run` with an array.
- `app/Support/PayrollSchema.php` calls `new Blueprint(` and `setConnection(`.
- `config/filesystems.php` has no `local` disk.
- `routes/web.php` declares the route name `profile` twice.
- `php -l` passes on every file.

### Relevant Context
- The stub does not run. Bob only reads it.
- The inventory counts stay small and true. The report never pads them.
- Every planted item maps to a row in the breaking-change file.

---

## Sub-Task 8 — Update AGENTS.md

**Status:** [x] done

### Intent
Record the toolkit, split the commands between teammates, and state the
workflow in the required four fields.

### Expected Outcomes
- `AGENTS.md` holds the toolkit statement and the owner table.
- The workflow block uses sentences under 20 words.
- The skill structure block shows the real `.bob/` path.
- Two new rules forbid memory-based compatibility claims and invented findings.

### Relevant Context
- Never name a script `bob`. Bob Shell owns that name.
- `.opencode/` stays ignored. Third-party skills live there.

---

## Sub-Task 9 — Verify end to end

**Status:** [ ] blocked, needs Bob Shell

### Intent
Prove the workflow on a real project, as the hackathon requires.

### Expected Outcomes
- `bob-upgrade` prints a risk report on `sample-app/`.
- The report finds the planted items and invents nothing.
- The report shows the true counts from `preflight.py`.

### Relevant Context
- Bob Shell 2.0 needs Node.js 24 or later. The machine runs Node 22.16.0.
- Install Bob Shell, then run `bob-upgrade` at the repository root.
- A team member owns `bob-pr`. Do not change `bob-pr/`.
