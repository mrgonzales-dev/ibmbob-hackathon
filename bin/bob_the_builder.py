import argparse
import shutil
import subprocess
import sys
from pathlib import Path

WIDTH = 46
TAGLINE = "B O B  T H E  B U I L D E R"
LANE_COUNT = 3
ART_ROWS = (
    "  \u2588\u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557",
    "  \u2588\u2588\u255c\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u255c\u2550\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u255c\u2550\u2550\u2588\u2588\u2557",
    "  \u2588\u2588\u2588\u2588\u2588\u2588\u255d\u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u255d",
    "  \u2588\u2588\u255c\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u255c\u2550\u2550\u2588\u2588\u2557",
    "  \u2588\u2588\u2588\u2588\u2588\u2588\u255d\u255a\u2588\u2588\u2588\u2588\u2588\u2588\u255d\u2588\u2588\u2588\u2588\u2588\u2588\u255d",
    "  \u255a\u2550\u2550\u2550\u2550\u2550\u255d  \u255a\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u2550\u2550\u2550\u2550\u255d",
)
BLOCK_MARKERS = (">-", ">", "|", "|-")


class DataError(ValueError):
    pass


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


SKILL_PARENTS = ("", "skills", ".bob/skills")


def skill_dirs(root):
    """Return every skill folder under a project root.

    A skill is a folder that holds a SKILL.md. In this repository each skill
    sits under skills/. Bob Shell reads .bob/skills/, and a plain folder works
    for a stand-alone install, so the search accepts all three places.
    """
    base = Path(root)
    found = []
    for parent in SKILL_PARENTS:
        holder = base / parent if parent else base
        if not holder.is_dir():
            continue
        found.extend(
            sorted(
                entry
                for entry in holder.iterdir()
                if entry.is_dir()
                and not entry.name.startswith(".")
                and (entry / "SKILL.md").is_file()
            )
        )
    return found


def is_toolkit_root(candidate):
    if (Path(candidate) / ".bob" / "skills").is_dir():
        return True
    return bool(skill_dirs(candidate))


def find_repo_root(start, stop=None):
    current = Path(start).resolve()
    boundary = Path(stop).resolve() if stop is not None else None
    for candidate in (current, *current.parents):
        if is_toolkit_root(candidate):
            return candidate
        if boundary is not None and candidate == boundary:
            break
    return None


def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise DataError("the file has no frontmatter block")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise DataError("the frontmatter block is not closed")
    data = {}
    key = None
    parts = []
    for line in lines[1:end]:
        if not line.strip():
            continue
        if line[0] in " \t":
            if key is not None:
                parts.append(line.strip())
            continue
        if key is not None:
            data[key] = " ".join(parts).strip()
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        parts = [] if value in BLOCK_MARKERS else [value]
    if key is not None:
        data[key] = " ".join(parts).strip()
    return data


def first_sentence(text, limit=46):
    text = " ".join(text.split())
    if not text:
        return ""
    end = text.find(". ")
    if end != -1:
        text = text[: end + 1]
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.rstrip(" ,;:") + "\u2026"


def read_skill(path):
    target = Path(path)
    if not target.is_file():
        return None
    try:
        data = parse_frontmatter(target.read_text(encoding="utf-8"))
    except (DataError, OSError, UnicodeDecodeError):
        return None
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    if not name or not description:
        return None
    return name, first_sentence(description)


def list_skills(root):
    found = []
    for entry in skill_dirs(root):
        item = read_skill(entry / "SKILL.md")
        if item is not None:
            found.append(item)
    found.sort(key=lambda pair: pair[0])
    return found


def _center(text, inner):
    pad = inner - len(text)
    if pad <= 0:
        return text
    left = pad // 2
    return " " * left + text


def _box_row(content, inner):
    return "\u2502 " + content.ljust(inner) + " \u2502"


def _status(skills):
    count = len(skills)
    commands = "command" if count == 1 else "commands"
    if count == 1:
        return f"{count} {commands} ready, {LANE_COUNT} lanes inside"
    return f"{count} {commands} ready"


def render_banner(skills, width=WIDTH):
    inner = width - 2
    lines = ["\u256d" + "\u2500" * width + "\u256e"]
    lines.append(_box_row("", inner))
    for row in ART_ROWS:
        lines.append(_box_row(row, inner))
    lines.append(_box_row("", inner))
    lines.append(_box_row(_center(TAGLINE, inner), inner))
    lines.append(_box_row("", inner))
    lines.append("\u2570" + "\u2500" * width + "\u256f")
    lines.append("")
    lines.append("  Your AI engineering toolkit.")
    lines.append("")
    if skills:
        widest = max(len("/" + name) for name, _ in skills)
        for name, tagline in skills:
            lines.append("  " + ("/" + name).ljust(widest + 3) + tagline)
    else:
        lines.append("  No commands installed.")
    lines.append("")
    lines.append("  " + "\u2500" * inner)
    lines.append("")
    lines.append("  " + _status(skills))
    return "\n".join(lines)


def launch_chat(root):
    executable = shutil.which("bob")
    if executable is None:
        print("bob not found on PATH.", file=sys.stderr)
        print(
            "Install Bob Shell 2.0: "
            "https://bob.ibm.com/docs/shell/getting-started/install-and-setup",
            file=sys.stderr,
        )
        return 1
    return subprocess.call([executable, "chat"], cwd=str(root))


def main(argv=None, stop=None):
    _force_utf8()
    parser = argparse.ArgumentParser(
        prog="bob-the-builder",
        description="Start the Bob the Builder toolkit session.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="the toolkit project directory, or a subdirectory of it",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="start an interactive Bob session after the banner",
    )
    parser.add_argument(
        "--banner-only",
        action="store_true",
        help="print the banner and exit, which is the default",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    root = find_repo_root(args.path, stop=stop)
    if root is None:
        print(
            f"error: not a Bob toolkit project: no .bob/skills "
            f"directory above {args.path}",
            file=sys.stderr,
        )
        return 1

    skills = list_skills(root)
    print(render_banner(skills))

    if args.chat:
        return launch_chat(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
