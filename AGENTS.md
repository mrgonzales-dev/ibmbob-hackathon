# AGENTS.md

## Hackathon Problem Statement

> Create a solution that improves a specific developer workflow, such as
> onboarding, debugging, code review, testing, application maintenance, or
> release and deployment processes.
>
> Start by clearly defining a problem where time, effort, or errors are too
> high today. Then, using IBM Bob 2.0, build a working prototype on a real or
> sample project that demonstrates a full solution to improve the specified
> workflow.
>
> Leverage features like Agent mode, parallel tasks, subagents, and document
> understanding to manage and improve multiple steps, not just assist with
> coding. Clearly demonstrate impact by showing how your solution increases
> productivity, reduces manual effort, errors, and rework, or significantly
> shortens the time required to complete tasks.

### Our toolkit

> A terminal-native AI developer toolkit that understands your entire codebase
> and helps you build, debug, review, and maintain it.

We build at the repository root. All skills ship inside the `bobdevkit/`
package folder. On install, a skill folder maps to
`<agent-config>/skills/<name>/` in a project. Git tracks every file, so
every command ships as a skill a teammate gets on clone.

A **skill** is one user-facing command. The user types it, or a model activates
it from its description. Skills are agent-agnostic — any AI agent that reads
a `SKILL.md` from its skills directory can use them.

| Command | Purpose |
|---|---|
| `bob-upgrade-check` | Ranked upgrade risk report. Scans deps, APIs, and config. Merges into one HIGH/MED/LOW table. |
| `bob-impact` | Change impact (blast radius) report. Traces callers, tables, and tests from git diff. |
| `bob-pr` | Plan-as-PR review gate. Serves a plan on localhost. Waits for approve or request-changes before any file is touched. |

The lanes inside each skill are internal steps, not separate commands.
The `bob-upgrade-check` scanner runs all three lanes (`deps`, `apis`, `config`)
in one pass and needs no thread pool. The whole scan takes about 13 ms on the
18-file sample app. On the `--ai` path the agent gives each lane its own
`explore` subagent. Never copy the rule table into a second file. Link
the shared reference.

Each AI agent reads skills from its own config directory:

| Agent | Project skills dir | Global skills dir |
|---|---|---|
| IBM Bob | `.bob/skills/` | `~/.bob/skills/` |
| Devin | `.devin/skills/` | — |
| Claude Code | `.claude/skills/` | — |
| Cursor | `.cursor/skills/` | — |

A project copy wins over the global copy. For agents not listed above,
check their documentation for the correct skills directory.

Each skill is self-contained. A skill folder holds everything that skill needs,
so one skill is one folder:

```
<skill-name>/
  SKILL.md          # required: frontmatter + instructions
  src/              # required: all scripts and data the skill needs
    run.py          # the command: local scan, optional --ai to Bob Shell
    <scanner>.py    # the local rule engine
    *.md            # the rule reference and the report template
    requirements.txt
    tests/
```

### Our workflow

| Workflow | Pain today | Solution | Impact |
|---|---|---|---|
| Dependency upgrade before a major version bump | Developers read changelogs and check packages by hand. The work takes two to four hours. A missed package causes a broken deploy. | `bob-upgrade-check` scans the whole project against a committed rule table. It prints one ranked HIGH/MED/LOW report. After you approve, the agent writes the upgrade plan. | A Laravel 11 → 12 upgrade analyzed in 13 ms on the 18-file sample app. |
| Change impact before a merge | Developers grep callers by hand and miss tests and tables. A change ships blind. | `bob-impact` traces the changed files to direct callers, database tables, and tests. It prints one ranked blast-radius report. | The blast radius is visible before the merge, not after the deploy breaks. |
| Plan review before code | A plan goes straight to code. The reviewer sees the change too late. | `bob-pr` serves the plan as a localhost pull-request page. You approve or request changes before any real file is touched. | Bad plans stop at the plan, not at the broken build. |

## Skill Structure

Every skill lives in its own directory inside `bobdevkit/` and must
contain a `SKILL.md`. The `bobdevkit/SKILL.md` at the package root is the
global installer skill — it instructs the agent to copy the three skill
folders into the project's agent config dir.

```
<repo root>
  bobdevkit/          # the skill package
    SKILL.md          # global installer: frontmatter + copy instructions
    <skill-name>/
      SKILL.md          # required: frontmatter + instructions
      src/              # required: all scripts and data the skill needs
      agents/<persona>.md # optional: one role for a subagent
      commands/<name>.md  # optional: a slash command
  tests/              # test suites, kept outside the shipped package
    <skill-name>/
```

Bob Shell reads `.bob/skills/` at the project root, and each skill folder
in `bobdevkit/` installs into that directory. Git tracks the package, so a
teammate receives every command on clone. Do not put a hackathon skill in
`.opencode/`. That directory holds throwaway third-party skills and is
ignored.

`SKILL.md` format:

```markdown
---
name: skill-name        # lowercase, hyphens, matches directory name
description: >-         # 1-3 sentences: what it does AND when to use it.
  One line per trigger. Include trigger phrases users would say.
---

# Skill Name

Step-by-step instructions for the agent...
```

## Agent Behavior

- Follow the skill structure exactly; do not invent extra directories or files.
- Make the smallest change that satisfies the request; no speculative features.
- When writing or editing a skill, keep the human's intent in `description`
  triggers — optimize for the skill being invoked at the right time.
- Prefer editing an existing skill over creating a new one.
- If a request is ambiguous, ask before building.
- Never commit secrets, API keys, or generated artifacts to the repo.
- Flag violations of these rules instead of silently working around them.
- Never state a compatibility fact from memory. Read it from the official
  documentation or a committed data file, then name the source.
- Never invent a finding to fill a report. Report nothing when nothing breaks.

## Git Commit Rules

- Do not add the agent as a collaborator. Do not write `Co-Authored-By`,
  `Generated with`, or `Signed-off-by` trailers (metadata lines at the end
  of a commit message) for the agent.
- Use conventional commits (the `type: subject` format). Use `feat:`,
  `fix:`, `docs:`, `refactor:`, `test:`, or `chore:`.
- Write the subject line in the imperative mood. Write "Add login page",
  not "Added login page".
- Keep the subject line at 50 characters or less. Do not end it with a
  period.
- Use the commit body to explain the why, not the what. Wrap the body at
  72 characters.
- Make atomic commits (one logical change per commit). Do not mix
  unrelated changes in one commit.
- Run `git status` and `git diff` before the commit. Stage only the files
  that belong to the change.
- Do not commit secrets, API keys, or generated artifacts.
- Do not push, force-push, or rewrite history unless the user asks.
- Do not commit when no changes exist.

## Communication Standard — ASD-STE100

All AI-generated text (chat, reports, code comments, documentation,
explanations) must obey ASD-STE100 Simplified Technical English rules:

- **Approved words only.** Use the STE100 approved-word list. Do not use
  synonyms — one word has one meaning (e.g., use "start" not "commence").
- **IT and computer jargon is permitted.** Technical terms not in the STE100
  word list (e.g., "database", "endpoint", "middleware", "refactor",
  "deployment") are allowed and treated as approved within their domain.
- **Explain every jargon term in parentheses.** When a technical term, code
  identifier, or abbreviation appears in a question, explanation, or report,
  add a short plain-English meaning in parentheses right after it (e.g.,
  "DTR (the daily timesheet row)", "swap (rewrite the values to the approved
  ones)"). Do this every time the term is used, not only the first time.
- **Maximum 20 words per sentence.** Break long sentences into two or more.
- **One topic per sentence.** Do not combine unrelated ideas.
- **Active voice only.** Write "the function returns a value", not "a value
  is returned by the function".
- **Imperative mood for instructions and procedures.** Write "Write the
  test", not "You should write the test".
- **Present tense for facts and descriptions.** Do not use past tense for
  procedures.
- **Articles before nouns.** Use "the", "a", or "an" before nouns where
  applicable.
- **No -ing verb forms for instructions.** Write "Remove the file", not
  "Removing the file".
- **Short words over long words.** If two words mean the same thing, use the
  shorter one.
- **No hidden verbs.** Write "decide" not "make a decision", "test" not
  "perform a test".
- **No redundant pairs.** Do not write "each and every" or "first and
  foremost".

## Code Review Preferences

- **Be brutal and thorough.** Double-check code changes, especially when
  modifying existing patterns. Look for hidden complexity before making
  changes, not after. When in doubt, ask and confirm.
- **Review all connected files first.** Before planning any change, read
  every file that touches or depends on the code you are about to modify.
  Trace function calls, imports, includes, injections, and shared state. Do
  not plan a change until you have read and understood the full chain of
  affected files.
- **Double-check all connected files after planning.** Once you have a plan,
  re-read the connected files to confirm the plan does not break existing
  logic, return structures, side effects, or assumptions made by callers. If
  a connected file relies on a behavior you are about to change, flag it
  before proceeding.

## Test Policy

- **Golden rule:** When making tests, maintain 1:1 logic with the code being
  tested. The test must verify the exact behavior of the code, not an
  approximation.
- **Test-driven development for new modules.** When building a new module,
  write the tests first. The tests define the expected behavior. Then write
  the code to make the tests pass. The cycle is: write test, present to user
  for review, get approval, write code, run test, fix until passing.
- After writing tests, present them to the user for review before running
  them. Do not run tests until the user approves the test code.
- Do not edit existing tests unless the user explicitly says so.
- Do not run the test suite unless the user explicitly says so.

## Explanation and Reporting

- **Always use a behavior table.** When explaining or reporting on code,
  logic, calculations, or comparisons, present the information in a table
  with columns for the behavior, condition, and result. Do not use long
  paragraphs where a table communicates the same information more clearly.
- **Always include a technical explanation and a layman explanation.** Every
  report or explanation must have both. The technical explanation describes
  the code, logic, and data flow. The layman explanation describes what it
  means in plain language without jargon.
- **Always end with a one-sentence explanation.** At the end of both the
  technical section and the layman section, add exactly one sentence that
  summarizes the point. This sentence must stand alone and make sense
  without reading the rest of the section.

## Rules

- One skill per directory; directory name == `name` in frontmatter.
- `description` must state both what the skill does and when to invoke it
  (it is the only thing the agent sees before loading the skill).
- Keep `SKILL.md` concise; everything the skill needs to run lives in `src/`
  and is referenced from `SKILL.md`, so it only loads when needed.
- Skills must be model-agnostic markdown instructions — no hardcoded tool
  names unless the skill requires them.
- Scripts must be runnable and documented inside `SKILL.md`.
- Never name a script `bob`. Bob Shell owns that command name. A file called
  `bob` breaks the shell itself. Use `bob-<command>` instead.
- Test each skill against a real or sample project before calling it done —
  the hackathon requires a demonstrated workflow, not just code.
