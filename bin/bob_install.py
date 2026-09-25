import argparse
import filecmp
import shutil
import sys
from pathlib import Path

TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = ("bob-upgrade",)


def global_root():
    return Path.home() / ".bob" / "skills"


IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def _files(base):
    return sorted(
        p.relative_to(base)
        for p in base.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )


def same_tree(left, right):
    left_files = _files(left)
    right_files = _files(right)
    if left_files != right_files:
        return False
    for relative in left_files:
        if not filecmp.cmp(left / relative, right / relative, shallow=False):
            return False
    return True


def install(destination=None, dry_run=False):
    destination = destination or global_root()
    results = []
    for name in SKILL_NAMES:
        source = TOOLKIT_ROOT / ".bob" / "skills" / name
        target = destination / name
        if not source.is_dir():
            results.append((name, "missing in the toolkit"))
            continue
        if target.is_dir() and same_tree(source, target):
            results.append((name, "already current"))
            continue
        if not dry_run:
            destination.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                shutil.rmtree(target)
            shutil.copytree(source, target, ignore=IGNORE)
        results.append((name, "would install" if dry_run else "installed"))
    return destination, results


def uninstall(destination=None, dry_run=False):
    destination = destination or global_root()
    removed = []
    for name in SKILL_NAMES:
        target = destination / name
        if target.is_dir():
            if not dry_run:
                shutil.rmtree(target)
            removed.append(name)
    return destination, removed


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="bob-install",
        description="Install the Bob the Builder skills for every project.",
    )
    parser.add_argument("--to", help="override the destination directory")
    parser.add_argument("--uninstall", action="store_true", help="remove the skills")
    parser.add_argument("--dry-run", action="store_true", help="show the plan only")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.uninstall:
        destination, removed = uninstall(args.to, args.dry_run)
        if not removed:
            print(f"Nothing to remove in {destination}")
            return 0
        verb = "would remove" if args.dry_run else "removed"
        for name in removed:
            print(f"{verb} {name}")
        print(f"Destination: {destination}")
        return 0

    destination, results = install(args.to, args.dry_run)
    for name, status in results:
        print(f"{status:<18} {name}")
    print("")
    print(f"Skills are global. Bob reads {destination} in every project.")
    print("A project copy in .bob/skills/ wins over the global copy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
