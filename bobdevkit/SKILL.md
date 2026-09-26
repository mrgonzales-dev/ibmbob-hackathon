---
name: bobdevkit
description: >-
  The Bob devkit package and installer. Holds the three skills
  (bob-upgrade-check, bob-impact, bob-pr) and copies them into the skills
  directory of whatever AI agent the project uses. Use when the user says
  "install the devkit", "set up the skills", "add the skills to this
  project", "install bobdevkit", or "activate the devkit in this project".
---

# Bob DevKit

You install the three devkit skills into whatever AI agent config dir the
project uses. You copy folders. You do not run a script. This skill is
agent-agnostic — it works with any agent that reads a skills directory.

## The three skills

The skill folders sit next to this `SKILL.md`, inside `bobdevkit/`:

| Skill | Folder | What it does |
|---|---|---|
| `bob-upgrade-check` | `bobdevkit/bob-upgrade-check/` | Ranked upgrade risk report before a major framework bump. |
| `bob-impact` | `bobdevkit/bob-impact/` | Change impact (blast radius) analyzer for a diff or file. |
| `bob-pr` | `bobdevkit/bob-pr/` | Presents a plan as a reviewable PR page the user approves first. |

## The agent config dirs

Each AI agent reads skills from its own config dir. Check which one the
project uses. The table below lists the known locations. Mark any path
not listed here as unverified and tell the user to confirm before copying.

| Agent | Config dir | Skills dir | Verified |
|---|---|---|---|
| Bob / IBM Bob | `.bob/` | `.bob/skills/` | Yes |
| Devin | `.devin/` | `.devin/skills/` | Check your Devin docs |
| Claude Code | `.claude/` | `.claude/skills/` | Check your Claude docs |
| Cursor | `.cursor/` | `.cursor/skills/` | Check your Cursor docs |
| Other agents | check their docs | — | — |

## Phase 1 — Detect

List the project root. Check which of these config dirs exist:

```
.bob/
.devin/
.claude/
.cursor/
```

Print the ones you found in one line. If none exist, ask the user which
agent they use and whether to create the config dir.

## Phase 2 — Copy

For each detected agent, copy the three skill folders into its skills dir.
The source root is the parent of this `bobdevkit/` folder (the repo root).
Run the copy commands from there.
Replace `<config-dir>` with the agent's config dir from the table above.
Skip `__pycache__/` and `*.pyc` files.

### macOS and Linux

```shell
cp -r bobdevkit/bob-upgrade-check <config-dir>/skills/bob-upgrade-check
cp -r bobdevkit/bob-impact        <config-dir>/skills/bob-impact
cp -r bobdevkit/bob-pr            <config-dir>/skills/bob-pr
```

### Windows PowerShell

```powershell
Copy-Item -Recurse bobdevkit\bob-upgrade-check <config-dir>\skills\bob-upgrade-check
Copy-Item -Recurse bobdevkit\bob-impact        <config-dir>\skills\bob-impact
Copy-Item -Recurse bobdevkit\bob-pr            <config-dir>\skills\bob-pr
```

When the skills dir does not exist yet, create it first:

```shell
mkdir -p <config-dir>/skills        # macOS / Linux
New-Item -ItemType Directory <config-dir>\skills   # Windows
```

## Phase 3 — Report

Print one line per skill you installed. Use this shape:

```
Installed bob-upgrade-check into .bob/skills/bob-upgrade-check
Installed bob-impact        into .bob/skills/bob-impact
Installed bob-pr            into .bob/skills/bob-pr
```

When you installed into more than one agent, print one block per agent
separated by a blank line. End with one line that names every agent you
installed into.

## Rules

| Rule | Why |
|---|---|
| Copy the whole skill folder, not just the `SKILL.md` | Each skill needs its `src/` scripts and data. |
| Copy from inside `bobdevkit/` | The skills live inside the package, not at the repo root. |
| Skip `__pycache__/` and `*.pyc` | These are build artifacts, not source. |
| Skip `scratch.txt` | Working notes, not part of the skill. |
| Overwrite an existing skill | A re-install replaces a stale copy. |
| Never delete a config dir or a skill you did not install | The user may have other skills there. |
| Never commit the installed copies | They live in agent config dirs, not the devkit repo. |
