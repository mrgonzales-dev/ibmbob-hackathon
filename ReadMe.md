# IBM Bob 2.0 Hackathon — Bob Devkit

A terminal-native AI developer toolkit built on **IBM Bob 2.0**. Each command
ships as a self-contained **skill** (one folder, one `SKILL.md`). A teammate
gets every command on `git clone`, because Git tracks the whole repo.

The devkit improves the **dependency upgrade** and **change impact**
developer workflows. Today these jobs take hours of manual changelog reading
and miss packages that break production. Bob scans the whole project against
a committed rule table, prints a ranked report, then writes the upgrade plan
after you approve it.

> Built for the IBM Bob 2.0 hackathon. The problem statement: improve a
> developer workflow (onboarding, debugging, code review, testing,
> maintenance, or release) using Agent mode, parallel tasks, subagents, and
> document understanding.

---

## Why this workflow

| Workflow | Pain today | Bob solution | Impact |
|---|---|---|---|
| Dependency upgrade before a major bump | Developers read changelogs and check packages by hand. The work takes two to four hours. A missed package breaks the deploy. | Bob scans the project against a committed rule table. It prints one ranked HIGH/MED/LOW report. After you approve, it writes the plan. | A Laravel 11 to 12 upgrade analyzed in about 13 ms on an 18-file project. |
| Change impact before a merge | Developers grep callers by hand and miss tests and tables. A change ships blind. | Bob traces the changed files to direct callers, database tables, and tests. It prints one ranked blast-radius report. | The blast radius is shown before the merge, not after the deploy breaks. |
| Plan review before code | A plan goes straight to code. The reviewer sees the change too late. | Bob serves the plan as a localhost pull-request page. You approve or request changes before any real file is touched. | Bad plans stop at the plan, not at the broken build. |

---

## Skills

All skills ship inside the `bobdevkit/` package folder. Install a skill by
copying its folder to `~/.bob/skills/` (global) or `.bob/skills/` (per
project). A project copy wins over the global copy.

| Skill | Command | What it does |
|---|---|---|
| `bob-upgrade-check` | `bob-upgrade-check` | Major framework upgrade risk analyzer. Scans a PHP project for the package, code, and config changes a version bump causes. Returns one ranked HIGH/MED/LOW report and an optional phased plan. |
| `bob-impact` | `bob-impact` | Change impact analyzer. Reads `git diff`, traces the direct callers, database tables, and tests that reference the changed code. Prints one ranked blast-radius report. Add `--regress` to run the affected tests. |
| `bob-pr` | `bob-pr` | Serves a plan as a GitHub-style pull-request page on localhost. You approve or request changes before any real project file is touched. |
| `bobdevkit` | `bobdevkit` | The package and installer. Holds all three skills. Its `SKILL.md` detects which AI agent config dir the project uses and copies the skills into it. Agent-agnostic. |

### Skill structure

```
<repo root>
  bobdevkit/          # the skill package: installer SKILL.md + the skills
    <skill-name>/
      SKILL.md          # required: frontmatter + instructions
      src/              # required: all scripts and data the skill needs
        run.py          # the command: local scan, optional --ai to Bob Shell
        <scanner>.py    # the local rule engine
        *.md            # the rule reference and the report template
        requirements.txt
  tests/              # test suites, kept outside the shipped package
    <skill-name>/
```

A skill is model-agnostic markdown. The local scanner needs no API key and
no model. Add `--ai` to hand the skill to Bob Shell, which needs a key.

---

## Repository layout

| Path | Purpose |
|---|---|
| `bobdevkit/` | The skill package: global installer `SKILL.md` plus the three skill folders. |
| `bobdevkit/bob-upgrade-check/` | The upgrade risk analyzer skill. |
| `bobdevkit/bob-impact/` | The change impact analyzer skill. |
| `bobdevkit/bob-pr/` | The plan-as-PR review gate skill. |
| `bob-devkit-landing-page/` | Vue 3 + Vite landing page for the demo. |
| `AGENTS.md` | The agent rules: toolkit, workflow, skill structure, commit rules, and the ASD-STE100 communication standard. |

---

## Get started

### Option A — Clone the full repo

```shell
git clone https://github.com/mrgonzales-dev/ibmbob-hackathon.git
cd ibmbob-hackathon
```

All three skills sit inside `bobdevkit/`. Copy the ones you need to
`~/.bob/skills/` so Bob finds them in every project:

```shell
# macOS / Linux
cp -r bobdevkit/bob-upgrade-check ~/.bob/skills/
cp -r bobdevkit/bob-impact        ~/.bob/skills/
cp -r bobdevkit/bob-pr            ~/.bob/skills/

# Windows PowerShell
Copy-Item -Recurse bobdevkit\bob-upgrade-check $HOME\.bob\skills\
Copy-Item -Recurse bobdevkit\bob-impact        $HOME\.bob\skills\
Copy-Item -Recurse bobdevkit\bob-pr            $HOME\.bob\skills\
```

### Option B — Download one skill without cloning

Use `npx degit` to pull a single skill folder straight into your project's
`.bob/skills/` directory. No `git clone` needed.

```shell
# upgrade risk analyzer
npx degit mrgonzales-dev/ibmbob-hackathon/bobdevkit/bob-upgrade-check .bob/skills/bob-upgrade-check

# change impact analyzer
npx degit mrgonzales-dev/ibmbob-hackathon/bobdevkit/bob-impact .bob/skills/bob-impact

# plan-as-PR review gate
npx degit mrgonzales-dev/ibmbob-hackathon/bobdevkit/bob-pr .bob/skills/bob-pr
```

`npx degit` requires Node.js 16 or later. It downloads the folder contents
without the full Git history.

### Option C — Activate all skills from any AI agent chat

Paste the prompt below into any AI coding agent (Bob Shell, Claude Code,
Cursor, Devin, etc.). The agent runs all three `npx degit` commands, reads
each downloaded `SKILL.md`, and immediately follows its instructions. No
manual copy step needed.

> Run `npx degit mrgonzales-dev/ibmbob-hackathon/bobdevkit/bob-upgrade-check .bob/skills/bob-upgrade-check` then `npx degit mrgonzales-dev/ibmbob-hackathon/bobdevkit/bob-impact .bob/skills/bob-impact` then `npx degit mrgonzales-dev/ibmbob-hackathon/bobdevkit/bob-pr .bob/skills/bob-pr` and follow the generated skill instructions for all three now. Read the complete output of each, redirecting to a temporary file first if necessary. Resolve relative paths from the supporting-files directory each skill provides.

### Run the landing page

```shell
cd bob-devkit-landing-page
npm install
npm run dev
```

---

## How `bob-upgrade-check` works

`bob-upgrade-check` analyzes one project against one target version. It reads the
project. It never changes application code during the analysis.

| Phase | What happens |
|---|---|
| 0 — Detect | Read `composer.json`. Find the framework package and its installed version in `composer.lock`. Print the current and the target version. |
| 1 — Inventory | Run `preflight.py`. It counts files, packages, and tests. Its output is exact. |
| 2 — Three lanes | Run the `deps`, `apis`, and `config` lanes in parallel. Each lane is a read-only `explore` subagent with one role. |
| 3 — Merge and rank | Merge the three lists. Sort by severity, then by file path. Drop duplicates. Keep the highest severity. |
| 4 — Report | Print one table of findings. Print the source URL once, at the end. |
| 5 — Confirm, then plan | Ask the user before any plan. When the user wants a plan, order the work by severity. Put the HIGH items first. |

The three lanes keep separate contexts so the main thread stays small.

| Lane | Role | It reads | It must not read |
|---|---|---|---|
| `deps` | Package auditor | `composer.json`, `composer.lock` | Application code, `config/` |
| `apis` | Source auditor | Every PHP file | `composer.json` |
| `config` | Configuration auditor | `config/`, the code that reads disks | `composer.lock` |

The only source of breaking-change truth is
`bob-upgrade-check/src/laravel-12-breaking-changes.md`. No breaking change is ever
written from memory. Every row carries the impact rating that Laravel
publishes and a detect signal a search tool can match.

### Severity

| Severity | Meaning |
|---|---|
| HIGH | The upgrade breaks at runtime, or the build stops. |
| MED | The upgrade changes behavior in a way the code must answer. |
| LOW | The upgrade changes a default or a return shape. |

---

## How `bob-impact` works

`bob-impact` traces one change through a project. It reports only what a
grep-based trace can prove. It does not guess.

| Lane | Role | It reads | It must not read |
|---|---|---|---|
| `callers` | Direct caller tracer | Every PHP file except the changed files | The changed files |
| `tables` | Database table finder | The changed files only | Other files |
| `tests` | Test reference finder | Every file in `tests/` | Files outside `tests/` |

| Risk | Meaning |
|---|---|
| HIGH | The changed code has direct callers. A change can break them. |
| MED | No direct callers, but tests reference the changed code. |
| LOW | No callers and no tests. The change is isolated. |

Direct callers are marked as heuristic. Facades (Laravel static proxies)
and IoC (the dependency container) break naive tracing, so the report is
honest about that ceiling.

---

## How `bob-pr` works

`bob-pr` turns a plan into a reviewable pull-request page served on
localhost. All state lives in `.bob-pr/` under the project root. Never
store state globally.

1. Finish the plan. Do not write implementation code yet.
2. Run `new` to record the plan as PR revision 1.
3. Run `snapshot`. It copies each planned file into `.bob-pr/tmp/<id>/`
   and fingerprints the originals.
4. Make the planned edits on the shadow copies under `.bob-pr/tmp/<id>/`.
5. Run `diff`. Real unified diffs are computed and attached to the
   revision.
6. Run `serve` in the background. Tell the user the URL.
7. Wait for the user to say they reviewed it. Do not poll.
8. Run `decision <id>` and act on the verdict:
   - `APPROVED` — run `apply <id>` to install the shadow copies onto the
     real files.
   - `CHANGES_REQUESTED` — read the comment, edit the same shadow copies,
     run `revise`, run `diff`, then serve again.
   - `PENDING` — tell the user no decision was clicked yet.

`.bob-pr/` is a generated artifact. Never commit it.

---

## Rules the devkit follows

- One skill per directory. The directory name equals the `name` in the
  frontmatter.
- Never name a script `bob`. Bob Shell owns that command name.
- Never state a compatibility fact from memory. Read it from the official
  documentation or a committed data file, then name the source.
- Never invent a finding to fill a report. Report nothing when nothing
  breaks.
- Never change application code during an analysis. The user asked for a
  report.
- Never commit secrets, API keys, or generated artifacts.

See `AGENTS.md` for the full agent rules, the ASD-STE100 communication
standard, the commit rules, and the test policy.

---

## Technical and layman summary

**Technical:** The devkit is a set of model-agnostic skills. Each skill
runs a local Python scanner that needs no API key, then optionally hands
the skill to Bob Shell with `--ai`. The `bob-upgrade-check` scanner runs three
read-only subagent lanes (deps, apis, config) in parallel, merges and
ranks the findings against a committed rule table, and prints one
HIGH/MED/LOW report. The `bob-impact` scanner runs three grep lanes
(callers, tables, tests) in one pass and prints one blast-radius report.
The `bob-pr` skill serves a plan as a localhost pull-request page with an
explicit approve gate before any real file is touched. The whole
`bob-upgrade-check` scan takes about 13 ms on an 18-file project. The
devkit proves impact with a real workflow, not just code.

**Layman:** This toolkit helps a developer upgrade a big software project
without fear. The computer reads the project, finds the parts that will
break, and shows a short ranked list before any code changes. A second
tool shows what else in the project calls the code you just changed, so a
small edit does not break a faraway feature. A third tool shows the plan
as a web page you approve before the computer writes any code. The work
that took hours of manual reading now takes seconds.

The devkit turns a slow, error-prone manual job into a fast, checked,
ranked report.
