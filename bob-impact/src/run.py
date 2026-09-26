"""bob-impact command wrapper.

Runs the local scanner, or hands the skill to Bob Shell with --ai.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
SKILL_NAME = SRC_DIR.parent.name
TOOLKIT_ROOT = SRC_DIR.parents[1]
INSTALL_URL = "https://bob.ibm.com/docs/shell/getting-started/install-and-setup"
MAX_TURNS = "40"


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv=None):
    _force_utf8()
    parser = argparse.ArgumentParser(
        prog="bob-impact",
        description="Change impact analyzer. Traces a change through a PHP project.",
    )
    parser.add_argument("path", nargs="?", default=".", help="the project directory")
    parser.add_argument(
        "--file",
        action="append",
        help="analyze one named file (repeatable). Skips git diff.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--no-color", action="store_true", help="plain text even on a color terminal"
    )
    parser.add_argument(
        "--regress",
        action="store_true",
        help="after the report, run the tests that reference the changed code",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="hand the skill to Bob Shell instead of the local scanner",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    root = Path(args.path).resolve()

    if args.ai:
        return _run_with_bob(root, args)

    sys.path.insert(0, str(SRC_DIR))
    from impact import analyze, render, render_colored, run_regress

    report = analyze(root, files=args.file or None)

    if args.json:
        print(json.dumps(report, indent=2))
    elif args.no_color or not sys.stdout.isatty():
        print(render(report))
    else:
        printed = render_colored(report)
        if printed:
            print(printed)

    exit_code = 2 if report["count"] else 0

    if args.regress:
        print()
        print("=" * 60)
        print("REGRESSION")
        print("=" * 60)
        run_regress(root, report)

    return exit_code


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
        return 1

    files = " ".join(args.file) if args.file else ""
    goal = f"Analyze the impact of the changed files: {files or 'git diff'}."
    prompt = (
        f"{goal} Activate the {SKILL_NAME} skill from .bob/skills and run its "
        "full analysis. Report only what a grep trace can prove. Never invent "
        "a finding."
    )

    command = [
        executable,
        "run",
        "--mode",
        "agent",
        "--format",
        "json" if args.json else "pretty",
        "--max-turns",
        str(MAX_TURNS),
        prompt,
    ]
    return subprocess.call(command, cwd=str(root))


if __name__ == "__main__":
    sys.exit(main())
