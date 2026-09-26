"""Change impact scanner.

Traces a change through a PHP project. Reports only what a grep-based trace
can prove: direct callers, database tables, and tests that reference the
changed code. Never guesses business rules or indirect callers.
"""

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {"vendor", "node_modules", "storage", ".git", "dist", "build", "cache", ".bob-pr", ".bob"}
MAX_BYTES = 2_000_000

# class|interface|trait declarations. Capture the name. Skip the parent class
# after `extends` by only matching the first identifier on the line.
CLASS_DECL = re.compile(r"^\s*(?:class|interface|trait)\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)

# Table references. Match the four ways a Laravel file names a table.
TABLE_PATTERNS = [
    re.compile(r"protected\s+\$table\s*=\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"Schema::create\s*\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"DB::table\s*\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"->from\s*\(\s*['\"]([^'\"]+)['\"]"),
]


def _php_files(root):
    """Yield every PHP file under root, skipping vendor and other noise."""
    for path in sorted(Path(root).rglob("*.php")):
        if SKIP_DIRS.intersection(path.parts):
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        yield path


def _read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def extract_class_names(text):
    """Return the class, interface, and trait names declared in a file.

    Deduplicates and preserves first-seen order.
    """
    seen = []
    for match in CLASS_DECL.finditer(text):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def find_direct_callers(root, class_names, exclude_files):
    """Find PHP files that reference any of the changed class names.

    exclude_files holds the relative paths of the changed files so the
    scanner never reports a file as its own caller. The tests/ directory
    is skipped here because find_referencing_tests tracks test references
    separately.
    """
    if not class_names:
        return []
    exclude_set = {p.replace("\\", "/") for p in exclude_files}
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, class_names)) + r")\b")
    callers = []
    for path in _php_files(root):
        relative = path.relative_to(root).as_posix()
        if relative in exclude_set:
            continue
        if relative.startswith("tests/"):
            continue
        text = _read(path)
        if not text:
            continue
        match = pattern.search(text)
        if match:
            callers.append({"file": relative, "class": match.group(1)})
    callers.sort(key=lambda row: row["file"])
    return callers


def find_table_references(root, changed_file_paths):
    """Return the table names referenced in the changed files.

    Matches protected $table, Schema::create, DB::table, and ->from.
    Deduplicates and sorts.
    """
    tables = []
    seen = set()
    for relative in changed_file_paths:
        path = Path(root) / relative
        if not path.is_file():
            continue
        text = _read(path)
        for pattern in TABLE_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1)
                if name not in seen:
                    seen.add(name)
                    tables.append(name)
    tables.sort()
    return tables


def find_referencing_tests(root, class_names):
    """Find test files that reference any of the changed class names."""
    if not class_names:
        return []
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, class_names)) + r")\b")
    tests = []
    tests_dir = Path(root) / "tests"
    if not tests_dir.is_dir():
        return tests
    for path in sorted(tests_dir.rglob("*.php")):
        if SKIP_DIRS.intersection(path.parts):
            continue
        text = _read(path)
        if not text:
            continue
        match = pattern.search(text)
        if match:
            tests.append({
                "file": path.relative_to(root).as_posix(),
                "class": match.group(1),
            })
    tests.sort(key=lambda row: row["file"])
    return tests


def compute_risk(has_callers, has_tests):
    """Apply the risk rubric from src/risk-rules.md."""
    if has_callers:
        return "HIGH"
    if has_tests:
        return "MED"
    return "LOW"


def changed_files_from_git(root):
    """Read git diff --name-only at the root. Filter to PHP files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    files = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.endswith(".php"):
            files.append(line.replace("\\", "/"))
    return files


def analyze(root, files=None):
    """Run the full impact analysis. Return the report dict."""
    root = Path(root).resolve()
    changed = files if files is not None else changed_files_from_git(root)
    changed = [f.replace("\\", "/") for f in changed]

    class_names = []
    for relative in changed:
        path = root / relative
        if path.is_file():
            class_names.extend(extract_class_names(_read(path)))
    # Deduplicate while preserving order.
    seen = set()
    unique_names = []
    for name in class_names:
        if name not in seen:
            seen.add(name)
            unique_names.append(name)

    callers = find_direct_callers(root, unique_names, set(changed))
    tables = find_table_references(root, changed)
    tests = find_referencing_tests(root, unique_names)
    risk = compute_risk(bool(callers), bool(tests))

    return {
        "root": str(root),
        "changed_files": changed,
        "class_names": unique_names,
        "callers": callers,
        "tables": tables,
        "tests": tests,
        "risk": risk,
        "count": len(callers) + len(tables) + len(tests),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --- rendering ---

RISK_STYLE = {"HIGH": "bold red", "MED": "yellow", "LOW": "cyan"}


def render(report):
    """Plain-text report. Matches src/report-template.md."""
    lines = [
        "\u256d" + "\u2500" * 50 + "\u256e",
        "\u2502 BOB THE BUILDER",
        "\u2502 CHANGE IMPACT ANALYZER",
        "\u2570" + "\u2500" * 50 + "\u256f",
        "",
    ]

    if not report["changed_files"]:
        lines.append("Changed files: none")
        lines.append("")
        lines.append("No findings. The change is isolated.")
        lines.append("Risk: LOW")
        return "\n".join(lines)

    lines.append("Changed files:")
    for f in report["changed_files"]:
        lines.append(f"  {f}")
    lines.append("")

    if report["callers"]:
        lines.append("Direct callers (heuristic \u2014 facades and IoC may miss some):")
        for c in report["callers"]:
            lines.append(f"  {c['file']}          \u2192 {c['class']}")
    else:
        lines.append("Direct callers: none")
    lines.append("")

    if report["tables"]:
        lines.append("Database tables:")
        for t in report["tables"]:
            lines.append(f"  {t}")
    else:
        lines.append("Database tables: none")
    lines.append("")

    if report["tests"]:
        lines.append("Tests referencing changed code:")
        for t in report["tests"]:
            lines.append(f"  {t['file']}          \u2192 {t['class']}")
    else:
        lines.append("Tests referencing changed code: none")
    lines.append("")

    lines.append(f"Risk: {report['risk']}")
    lines.append("")
    lines.append(f"Findings: {report['count']}")
    lines.append("Rubric:   src/risk-rules.md")
    return "\n".join(lines)


def render_colored(report, no_color=False):
    """Colored report using rich. Falls back to plain text."""
    try:
        from rich.console import Console
    except ImportError:
        return render(report)

    console = Console(no_color=no_color, width=130)
    console.print("[bold]\u256d" + "\u2500" * 50 + "\u256e[/bold]")
    console.print("[bold]\u2502 BOB THE BUILDER[/bold]")
    console.print("[bold]\u2502 CHANGE IMPACT ANALYZER[/bold]")
    console.print("[bold]\u2570" + "\u2500" * 50 + "\u256f[/bold]")
    console.print()

    if not report["changed_files"]:
        console.print("Changed files: none")
        console.print()
        console.print("[green]No findings. The change is isolated.[/green]")
        console.print("Risk: [cyan]LOW[/cyan]")
        return ""

    console.print("[bold]Changed files:[/bold]")
    for f in report["changed_files"]:
        console.print(f"  {f}")
    console.print()

    if report["callers"]:
        console.print("[bold]Direct callers[/bold] [dim](heuristic \u2014 facades and IoC may miss some):[/dim]")
        for c in report["callers"]:
            console.print(f"  {c['file']}          \u2192 {c['class']}")
    else:
        console.print("[dim]Direct callers: none[/dim]")
    console.print()

    if report["tables"]:
        console.print("[bold]Database tables:[/bold]")
        for t in report["tables"]:
            console.print(f"  {t}")
    else:
        console.print("[dim]Database tables: none[/dim]")
    console.print()

    if report["tests"]:
        console.print("[bold]Tests referencing changed code:[/bold]")
        for t in report["tests"]:
            console.print(f"  {t['file']}          \u2192 {t['class']}")
    else:
        console.print("[dim]Tests referencing changed code: none[/dim]")
    console.print()

    style = RISK_STYLE.get(report["risk"], "")
    console.print(f"Risk: [{style}]{report['risk']}[/{style}]")
    console.print()
    console.print(f"[bold]Findings:[/bold] {report['count']}")
    console.print("[dim]Rubric:   src/risk-rules.md[/dim]")
    return ""


def run_regress(root, report):
    """Run the tests that reference the changed code.

    Uses php artisan test, then vendor/bin/phpunit as a fallback. Prints the
    command and its exit code. Does not interpret the output.
    """
    root = Path(root)
    candidates = [
        ["php", "artisan", "test"],
        ["vendor/bin/phpunit"],
    ]
    for cmd in candidates:
        if "/" in cmd[0]:
            executable = str(root / cmd[0])
            if not Path(executable).is_file():
                continue
        else:
            executable = shutil.which(cmd[0])
            if executable is None:
                continue
        run_cmd = [executable] + cmd[1:]
        print(f"$ {' '.join(cmd)}")
        result = subprocess.run(run_cmd, cwd=str(root))
        print(f"\nExit code: {result.returncode}")
        return result.returncode
    print("No test runner found. Tried: php artisan test, vendor/bin/phpunit.")
    return 1
