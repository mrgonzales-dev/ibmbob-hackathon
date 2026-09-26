import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MAX_TURNS = "40"
INSTALL_URL = "https://bob.ibm.com/docs/shell/getting-started/install-and-setup"
SRC_DIR = Path(__file__).resolve().parent
SKILL_NAME = SRC_DIR.parent.name
TOOLKIT_ROOT = SRC_DIR.parents[1]
SKILL_PARENTS = ("", "skills", ".bob/skills")


class DataError(ValueError):
    pass


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _skill_parent(base):
    """Return the folders that can hold a skill, in search order.

    The repository keeps each skill under skills/. Bob Shell reads
    .bob/skills/. A stand-alone install holds the skill directly.
    """
    root = Path(base)
    for parent in SKILL_PARENTS:
        holder = root / parent if parent else root
        if holder.is_dir():
            yield holder


def available_skills(root):
    """List skill folders under a root, at the root or under skills/."""
    names = []
    for holder in _skill_parent(root):
        for entry in sorted(holder.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if (entry / "SKILL.md").is_file() and entry.name not in names:
                names.append(entry.name)
    return names


def listable_skills(root, fallback=None):
    names = available_skills(root)
    if fallback is not None:
        for name in available_skills(fallback):
            if name not in names:
                names.append(name)
    return names


def _skill_dir(base, name):
    for holder in _skill_parent(base):
        candidate = holder / name
        if candidate.is_dir() and (candidate / "SKILL.md").is_file():
            return candidate
    return None


def resolve_skill(root, name, fallback=None):
    found = _skill_dir(root, name)
    if found is not None:
        return found
    if fallback is not None:
        found = _skill_dir(fallback, name)
        if found is not None:
            return found
    known = ", ".join(available_skills(root)) or "none"
    raise DataError(f"unknown command '{name}'. Available commands: {known}")


def build_prompt(skill, target):
    if len(target) > 1:
        goal = f"Upgrade {target[0]} to {target[1]}."
    elif len(target) == 1:
        goal = f"Upgrade {target[0]} to its next major version."
    else:
        goal = (
            "No target given. Read composer.json and composer.lock, find the "
            "framework package, and use its next major version."
        )
    return (
        f"{goal} Activate the {skill} skill from .bob/skills and run its full "
        "analysis. Report only what the official upgrade guide supports. "
        "Never invent a finding."
    )


LANES = {"bob-upgrade-check": "all"}


def main(argv=None):
    _force_utf8()
    parser = argparse.ArgumentParser(
        prog="bob-skill",
        description="Run one skill of the Bob the Builder toolkit. No API key needed.",
    )
    parser.add_argument("path", nargs="?", default=".", help="the project directory")
    parser.add_argument(
        "command", nargs="?", default=SKILL_NAME, help="the skill name to run"
    )
    parser.add_argument("target", nargs="*", help="upgrade target, e.g. 'laravel 12'; passed to Bob Shell on --ai")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--no-color", action="store_true", help="plain text even on a color terminal"
    )
    parser.add_argument("--list", action="store_true", help="list the commands and exit")
    parser.add_argument(
        "--ai",
        action="store_true",
        help="hand the skill to Bob Shell instead of the local scanner",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    root = Path(args.path).resolve()

    if args.list:
        for name in listable_skills(root, fallback=TOOLKIT_ROOT):
            print(name)
        return 0

    try:
        resolve_skill(root, args.command, fallback=TOOLKIT_ROOT)
    except DataError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.ai:
        return _run_with_bob(root, args)
    return _run_local(root, args.command, as_json=args.json, no_color=args.no_color)


def _run_local(root, command, as_json=False, no_color=False):
    lane = LANES.get(command)
    if lane is None:
        print(f"error: '{command}' has no local scanner. Use --ai.", file=sys.stderr)
        return 1
    sys.path.insert(0, str(SRC_DIR))
    from laravel12 import analyze, render, render_colored

    report = analyze(root, lane)
    if as_json:
        print(json.dumps(report, indent=2))
    elif no_color or not sys.stdout.isatty():
        print(render(report))
    else:
        printed = render_colored(report)
        if printed:
            print(printed)
    return 2 if report["findings"] else 0


def _run_with_bob(root, args):
    executable = shutil.which("bob")
    if executable is None:
        print("bob not found on PATH.", file=sys.stderr)
        print(f"Install Bob Shell 2.0: {INSTALL_URL}", file=sys.stderr)
        return 1

    if not os.environ.get("BOB_API_KEY"):
        print(
            "error: --ai needs BOB_API_KEY. The local scanner needs no key.",
            file=sys.stderr,
        )
        print(
            "Run without --ai for the local report, or mint a key at "
            "https://bob.ibm.com with Scope set to Inference.",
            file=sys.stderr,
        )
        return 1

    command = [
        executable,
        "run",
        "--mode",
        "agent",
        "--format",
        "json" if args.json else "pretty",
        "--max-turns",
        str(MAX_TURNS),
        build_prompt(args.command, args.target),
    ]
    return subprocess.call(command, cwd=str(root))


if __name__ == "__main__":
    sys.exit(main())
