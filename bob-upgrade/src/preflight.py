import argparse
import json
import sys
from pathlib import Path

COMPOSER_JSON = "composer.json"
COMPOSER_LOCK = "composer.lock"
SKIP_DIRS = {"vendor", "node_modules", "storage", ".git", "dist", "build", "cache", ".bob-pr", ".bob"}
FRAMEWORK_PACKAGES = (
    "laravel/framework",
    "symfony/framework-bundle",
    "django/django",
)


class DataError(ValueError):
    pass


def find_project_root(start):
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / COMPOSER_JSON).is_file():
            return candidate
    return None


def _read_json(path):
    label = path.name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DataError(f"{label} is not valid JSON at line {error.lineno}") from error
    except OSError as error:
        raise DataError(f"{label} could not be read: {error.strerror}") from error


def parse_composer_json(root):
    payload = _read_json(Path(root) / COMPOSER_JSON)
    if not isinstance(payload, dict):
        raise DataError("composer.json must hold a JSON object at the top level")
    require = payload.get("require") or {}
    require_dev = payload.get("require-dev") or {}
    if not isinstance(require, dict) or not isinstance(require_dev, dict):
        raise DataError("composer.json require and require-dev must be objects")
    return {"require": require, "require-dev": require_dev}


def parse_composer_lock(root):
    path = Path(root) / COMPOSER_LOCK
    if not path.is_file():
        return None
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise DataError("composer.lock must hold a JSON object at the top level")
    packages = payload.get("packages") or []
    packages_dev = payload.get("packages-dev") or []
    if not isinstance(packages, list) or not isinstance(packages_dev, list):
        raise DataError("composer.lock packages and packages-dev must be lists")
    return {"packages": packages, "packages-dev": packages_dev}


def _walk(root):
    base = Path(root)
    for path in base.rglob("*.php"):
        relative = path.relative_to(base)
        if SKIP_DIRS.intersection(relative.parts):
            continue
        yield path


def count_php_files(root):
    return sum(1 for _ in _walk(root))


def count_test_cases(root):
    base = Path(root)
    total = 0
    for path in base.rglob("*Test.php"):
        relative = path.relative_to(base)
        if SKIP_DIRS.intersection(relative.parts):
            continue
        if relative.parts and relative.parts[0] == "tests":
            total += 1
    return total


def _find_framework(require, lock):
    package = next((name for name in FRAMEWORK_PACKAGES if name in require), None)
    if package is None:
        return {"package": None, "constraint": None, "installed": None}
    installed = None
    if lock:
        for entry in lock["packages"] + lock["packages-dev"]:
            if isinstance(entry, dict) and entry.get("name") == package:
                installed = entry.get("version")
                break
    return {"package": package, "constraint": require[package], "installed": installed}


def build_report(root):
    base = Path(root)
    manifest = parse_composer_json(base)
    lock = parse_composer_lock(base)
    warnings = []
    if lock is None:
        warnings.append("composer.lock is missing, so installed versions are unknown.")
    framework = _find_framework(manifest["require"], lock)
    if framework["package"] is None:
        warnings.append("No framework package found in composer.json require.")
    dependencies = 0
    if lock is not None:
        dependencies = len(lock["packages"]) + len(lock["packages-dev"])
    return {
        "root": str(base.resolve()),
        "composer_json": True,
        "composer_lock": lock is not None,
        "php_files": count_php_files(base),
        "dependencies": dependencies,
        "test_cases": count_test_cases(base),
        "packages_required": len(manifest["require"]),
        "packages_required_dev": len(manifest["require-dev"]),
        "framework": framework,
        "warnings": warnings,
    }


def render_text(report):
    framework = report["framework"]
    lines = [
        "\u256d" + "\u2500" * 42 + "\u256e",
        "\u2502 BOB THE BUILDER",
        "\u2502 DEPENDENCY UPGRADE ANALYZER",
        "\u2570" + "\u2500" * 42 + "\u256f",
        "",
        f"Project: {report['root']}",
        "",
    ]
    if framework["package"]:
        lines.append(f"Framework:  {framework['package']} {framework['constraint'] or 'unknown'}")
        lines.append(f"Installed:  {framework['installed'] or 'unknown'}")
    else:
        lines.append("Framework:  not detected")
    lines.extend(["", "Inventory", "\u2500" * 42])
    lines.append(f"{'\u2713' if report['composer_json'] else '\u2717'} composer.json")
    if report["composer_lock"]:
        lines.append(f"{'\u2713'} composer.lock")
    else:
        lines.append(f"{'\u2717'} composer.lock (missing)")
    lines.append(f"{'\u2713'} {report['php_files']} PHP files")
    lines.append(f"{'\u2713'} {report['dependencies']} dependencies")
    lines.append(f"{'\u2713'} {report['test_cases']} test cases")
    if report["warnings"]:
        lines.extend(["", "Warnings", "\u2500" * 42])
        lines.extend(f"! {item}" for item in report["warnings"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="preflight",
        description="Count project files, packages, and tests before an upgrade audit.",
    )
    parser.add_argument("--root", default=".", help="Directory to inspect. Defaults to the current directory.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Output format.")
    args = parser.parse_args(argv)

    try:
        root = find_project_root(args.root)
    except OSError as error:
        print(f"preflight: {error}", file=sys.stderr)
        return 2

    if root is None:
        print(f"preflight: no {COMPOSER_JSON} found in {args.root} or any parent directory.", file=sys.stderr)
        return 1

    try:
        report = build_report(root)
    except DataError as error:
        print(f"preflight: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report), end="")

    return 0


def _force_utf8(stream):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass


if __name__ == "__main__":
    _force_utf8(sys.stdout)
    _force_utf8(sys.stderr)
    sys.exit(main())
