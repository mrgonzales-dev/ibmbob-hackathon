import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SEVERITIES = {"HIGH": 3, "MED": 2, "LOW": 1}
TARGET = "Laravel 12"
SKIP_DIRS = {"vendor", "node_modules", "storage", ".git", "dist", "build", "cache", ".bob-pr", ".bob"}
MAX_BYTES = 2_000_000

PACKAGE_RULES = [
    {
        "id": "DEP-001",
        "package": "laravel/framework",
        "required": "^12.0",
        "major": 12,
        "severity": "HIGH",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Set the constraint to ^12.0 and run composer update.",
    },
    {
        "id": "DEP-002",
        "package": "phpunit/phpunit",
        "required": "^11.0",
        "major": 11,
        "severity": "HIGH",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Set the constraint to ^11.0 and run composer update.",
    },
    {
        "id": "DEP-003",
        "package": "pestphp/pest",
        "required": "^3.0",
        "major": 3,
        "severity": "HIGH",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Set the constraint to ^3.0 and run composer update.",
    },
    {
        "id": "API-003",
        "package": "nesbot/carbon",
        "required": "^3.0",
        "major": 3,
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Update Carbon to ^3.0.",
    },
]

CODE_RULES = [
    {
        "id": "API-001",
        "pattern": r"\bHasVersion7Uuids\b",
        "severity": "MED",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Replace the trait with HasUuids.",
    },
    {
        "id": "API-002",
        # The alias line holds both names, so skip lines with the fix.
        "pattern": r"^(?!.*HasVersion4Uuids).*\bHasUuids\b",
        "severity": "MED",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Use HasVersion4Uuids to keep version 4 identifiers.",
    },
    {
        "id": "API-005",
        # Only a list destructure assumes order, so only it fires.
        "pattern": r"(?:^\s*\[|list\s*\().*Concurrency::run\s*\(",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Read each result under its own array key.",
    },
    {
        "id": "API-006",
        "pattern": r"(?<!:)(?<!::)\bresolve\s*\(\s*[A-Z]",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Accept the new default class property values.",
    },
    {
        "id": "API-004",
        # Imports never set a lifetime, so skip use lines and * 60 fixes.
        "pattern": r"^(?!\s*use\s)(?!.*\*\s*60).*\bDatabaseTokenRepository\b",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Multiply the token lifetime in minutes by 60.",
    },
    {
        "id": "API-008",
        "pattern": r"mergeIfMissing\s*\(\s*\[?\s*['\"][^'\"]*\.[^'\"]*['\"]",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Read the nested value in dot notation.",
    },
    {
        "id": "DB-001",
        # A schema argument limits results, so only empty calls fire.
        "pattern": r"\bget(Tables|Views|Types)\s*\(\s*\)",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Pass the schema argument to keep one schema.",
    },
    {
        "id": "DB-002",
        # The flag keeps short names, so skip lines with the flag.
        "pattern": r"\bgetTableListing\s*\((?![^)]*schemaQualified)",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Pass schemaQualified: false.",
    },
    {
        "id": "DB-003",
        # Two arguments hold the connection, so only one argument fires.
        "pattern": r"new\s+Blueprint\s*\((?![^)]*,)",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Pass the connection as the first argument.",
    },
    {
        "id": "DB-004",
        "pattern": r"->setConnection\s*\(",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Pass the connection to the constructor.",
    },
    {
        "id": "DB-005",
        "pattern": r"->getPrefix\s*\(",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Read the prefix from the connection.",
    },
    {
        "id": "DB-006",
        "pattern": r"->withTablePrefix\s*\(",
        "severity": "LOW",
        "source": "https://laravel.com/docs/12.x/upgrade",
        "fix": "Read the prefix from the connection.",
    },
]

RESOLVE_EXEMPT = re.compile(r"\w+\s*::[^\n]*\bresolve\s*\(")
LOCAL_DISK_USE = re.compile(r"Storage::disk\s*\(\s*['\"]local['\"]\s*\)")
LOCAL_DISK_KEY = re.compile(r"['\"]local['\"]\s*=>")


def severity_rank(value):
    return SEVERITIES.get(value, 0)


def compare_major(constraint, major):
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(constraint or ""))
    if match is None:
        return True
    return int(match.group(1)) >= major


def rules_for_lane(lane):
    if lane == "deps":
        return PACKAGE_RULES
    if lane == "apis":
        return CODE_RULES
    if lane == "config":
        return [
            {
                "id": "CFG-001",
                "severity": "LOW",
                "source": "https://laravel.com/docs/12.x/upgrade",
                "fix": "Define the local disk with root storage_path('app').",
            }
        ]
    if lane == "all":
        return PACKAGE_RULES + CODE_RULES + rules_for_lane("config")
    raise ValueError(f"unknown lane '{lane}'")


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _php_files(root):
    for path in sorted(Path(root).rglob("*.php")):
        if SKIP_DIRS.intersection(path.parts):
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        yield path


def _lock_versions(root):
    payload = _read_json(Path(root) / "composer.lock")
    if not payload:
        return {}
    found = {}
    for group in ("packages", "packages-dev"):
        for entry in payload.get(group) or []:
            if isinstance(entry, dict) and entry.get("name"):
                found.setdefault(entry["name"], entry.get("version", ""))
    return found


def find_dependency_findings(root):
    payload = _read_json(Path(root) / "composer.json")
    if not payload:
        return []
    constraints = {}
    for group in ("require", "require-dev"):
        for name, value in (payload.get(group) or {}).items():
            constraints.setdefault(name, value)
    installed = _lock_versions(root)

    findings = []
    for rule in PACKAGE_RULES:
        found = constraints.get(rule["package"])
        if found is None:
            continue
        if compare_major(found, rule["major"]):
            continue
        findings.append(
            {
                "rule": rule["id"],
                "lane": "deps",
                "severity": rule["severity"],
                "package": rule["package"],
                "required": rule["required"],
                "found": found,
                "installed": installed.get(rule["package"], ""),
                "fix": rule["fix"],
                "source": rule["source"],
            }
        )

    return findings


def find_source_findings(root):
    compiled = [(rule, re.compile(rule["pattern"])) for rule in CODE_RULES]
    findings = []
    for path in _php_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relative = path.relative_to(root).as_posix()
        for number, line in enumerate(text.splitlines(), start=1):
            if RESOLVE_EXEMPT.search(line):
                continue
            for rule, pattern in compiled:
                if pattern.search(line):
                    findings.append(
                        {
                            "rule": rule["id"],
                            "lane": "apis",
                            "severity": rule["severity"],
                            "file": relative,
                            "line": number,
                            "evidence": line.strip(),
                            "fix": rule["fix"],
                            "source": rule["source"],
                        }
                    )
    findings.sort(key=lambda row: (-severity_rank(row["severity"]), row["file"], row["line"]))
    return findings


def find_config_findings(root):
    config = Path(root) / "config" / "filesystems.php"
    if not config.is_file():
        return []
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if LOCAL_DISK_KEY.search(text):
        return []
    uses = []
    for path in _php_files(root):
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if LOCAL_DISK_USE.search(body):
            uses.append(path.relative_to(root).as_posix())
    if not uses:
        return []
    return [
        {
            "rule": "CFG-001",
            "lane": "config",
            "severity": "LOW",
            "file": uses[0],
            "also": uses[1:],
            "old": "storage/app",
            "new": "storage/app/private",
            "fix": "Define the local disk with root storage_path('app'), or move the reads.",
            "source": "https://laravel.com/docs/12.x/upgrade",
        }
    ]


LANES = {
    "deps": find_dependency_findings,
    "apis": find_source_findings,
    "config": find_config_findings,
}


def analyze(root, lane="all", target=TARGET):
    if lane not in LANES and lane != "all":
        raise ValueError(f"unknown lane '{lane}'")
    findings = []
    if lane == "all":
        for name in ("deps", "apis", "config"):
            findings.extend(LANES[name](root))
    else:
        findings.extend(LANES[lane](root))
    findings.sort(key=lambda row: -severity_rank(row["severity"]))
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": target,
        "lane": lane,
        "root": str(Path(root).resolve()),
        "findings": findings,
        "count": len(findings),
    }


SEVERITY_STYLE = {
    "HIGH": "bold red",
    "MED": "yellow",
    "LOW": "cyan",
}


EVIDENCE_LIMIT = 52
CONSOLE_WIDTH = 130


def change_text(row):
    found = row.get("found", row.get("evidence", row.get("old", "")))
    needed = row.get("required", row.get("new", ""))
    if needed:
        return f"{found} -> {needed}"
    text = " ".join(str(found).split())
    if len(text) > EVIDENCE_LIMIT:
        return text[: EVIDENCE_LIMIT - 1] + "…"
    return text


def where_text(row):
    where = row.get("file", row.get("package", ""))
    if "line" in row:
        where = f"{where}:{row['line']}"
    return where


def rows_for(report):
    out = []
    for row in report["findings"]:
        out.append(
            [
                row["severity"],
                row["rule"],
                where_text(row),
                change_text(row),
                row["fix"],
            ]
        )
    return out


HEADERS = ["SEVERITY", "RULE", "WHERE", "CHANGE", "FIX"]


def render(report):
    lines = [
        f"Target: {report['target']}",
        f"Root:   {report['root']}",
        f"Generated: {report['generated']}",
        "",
    ]
    if not report["findings"]:
        lines.append("No findings. The report lists nothing because nothing breaks.")
        return "\n".join(lines)

    rows = rows_for(report)
    widths = [
        max(len(HEADERS[i]), max(len(r[i]) for r in rows)) for i in range(len(HEADERS))
    ]

    def cell(value, width):
        if len(value) > width:
            return value[: width - 1] + "…"
        return value.ljust(width)

    lines.append(" | ".join(HEADERS[i].ljust(widths[i]) for i in range(len(HEADERS))))
    lines.append("-+-".join("-" * w for w in widths))
    for row in rows:
        lines.append(" | ".join(cell(row[i], widths[i]) for i in range(len(HEADERS))))
    lines.append("")
    lines.append(f"Findings: {report['count']}")
    lines.append("Source:  https://laravel.com/docs/12.x/upgrade")
    return "\n".join(lines)


def render_colored(report, no_color=False):
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        return render(report)

    console = Console(no_color=no_color, width=CONSOLE_WIDTH)
    console.print(f"[bold]Target:[/bold] {report['target']}")
    console.print(f"[bold]Root:[/bold]   {report['root']}")
    console.print(f"[bold]Generated:[/bold] {report['generated']}")
    console.print()

    if not report["findings"]:
        console.print(
            "[green]No findings.[/green] The report lists nothing because nothing breaks."
        )
        return ""

    table = Table(box=None, pad_edge=False, header_style="bold", expand=False)
    for header, width, ratio in (
        ("SEVERITY", 8, None),
        ("RULE", 7, None),
        ("WHERE", 26, 2),
        ("CHANGE", 34, 3),
        ("FIX", 38, 3),
    ):
        table.add_column(
            header, overflow="ellipsis", no_wrap=True, width=width, ratio=ratio
        )
    for row in rows_for(report):
        style = SEVERITY_STYLE.get(row[0], "")
        table.add_row(
            f"[{style}]{row[0]}[/{style}]" if style else row[0],
            row[1],
            row[2],
            row[3],
            row[4],
        )
    console.print(table)
    console.print(f"[bold]Findings:[/bold] {report['count']}")
    console.print("[dim]Source:  https://laravel.com/docs/12.x/upgrade[/dim]")
    return ""


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        prog="laravel12", description="Laravel 12 breaking change scanner. No API needed."
    )
    parser.add_argument("--root", default=".", help="the project directory")
    parser.add_argument(
        "--lane", default="all", choices=["all", "deps", "apis", "config"]
    )
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument(
        "--no-color", action="store_true", help="plain text even on a color terminal"
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    report = analyze(args.root, args.lane)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif args.no_color or not sys.stdout.isatty():
        print(render(report))
    else:
        rendered = render_colored(report)
        if rendered:
            print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
