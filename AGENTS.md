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

We build in `.bob/` so every command ships as a skill that git tracks.

A **skill** is one user-facing command. The user types it, or a model activates
it from its description.

| Command | Purpose |
|---|---|
| `bob-upgrade` | Ranked upgrade risk report. Runs every lane and merges them. |

One command covers the whole workflow. The lanes are internal steps, not
separate commands. The `deps`, `apis`, and `config` lanes run in parallel
inside the one skill, then merge. Never copy the rule table into a second
file. Link the shared reference.

Bob reads skills from `<project>/.bob/skills/` and from `~/.bob/skills/`. Run
`bob-install` to copy the skill to the global path so it works in every
project. A project copy wins over the global copy.

Each skill is self-contained. A skill folder holds everything that skill needs,
so one skill is one folder:

```
.bob/skills/bob-upgrade/
  SKILL.md          # required: frontmatter + instructions
  src/
    run.py          # the command: local scan, optional --ai to Bob Shell
    <scanner>.py    # the local rule engine
    *.md            # the rule reference and the report template
    requirements.txt
    tests/
```

`bin/` holds only toolkit-level files that no single skill owns: the banner,
the installer, and the PATH launchers. The launchers are the only files that
point at skill code, and they hold no logic.

### Our workflow

<!-- one-line: which workflow we are improving and the pain point -->

- Workflow: Dependency upgrade analysis before a major framework version bump.
- Pain today: Developers read changelogs and check packages by hand. The work takes hours.
- Errors reach production. A missed package causes a broken deploy.
- Solution: Bob scans the whole project in parallel. It prints a ranked risk report and a plan.
- Impact: A Laravel 11 to 12 upgrade analyzed in seconds. The manual work takes two to four hours.

## Skill Structure

Every skill lives in its own directory and must contain a `SKILL.md`.

```
.bob/
  skills/<skill-name>/
    SKILL.md          # required: frontmatter + instructions
    src/              # required: all scripts and data the skill needs
  agents/<persona>.md # optional: one role for a subagent
  commands/<name>.md  # optional: a slash command
```

Bob Shell reads `.bob/skills/` at the project root. Git tracks `.bob/`, so a
teammate receives every command on clone. Do not put a hackathon skill in
`.opencode/`. That directory holds throwaway third-party skills and is ignored.

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
