#!/bin/sh
# bobdevkit installer — installs the three Bob devkit skills into an AI
# agent's skills directory.
#
# From a clone:   ./install.sh [--global|--project] [--agent NAME] [--dir DIR] [--uninstall]
# One-liner:      curl -fsSL https://raw.githubusercontent.com/mrgonzales-dev/ibmbob-hackathon/main/bobdevkit/install.sh | sh
#
# Project scope (default): installs into every detected agent config dir
# in the current directory (.bob .devin .claude .cursor); creates
# .bob/skills when none exist. Global scope installs to the agent's home
# skills dir (default: ~/.bob/skills).
set -eu

REPO="mrgonzales-dev/ibmbob-hackathon"
BRANCH="main"
SKILLS="bob-upgrade-check bob-impact bob-pr"
SKILL_DIR_NAME="skills"

SCOPE="project"
AGENT=""
TARGET_DIR=""
UNINSTALL=0

usage() {
    cat <<'EOF'
Usage: install.sh [--project|--global] [--agent NAME] [--dir DIR] [--uninstall]

  --project     Install into detected agent config dirs in cwd (default)
  --global      Install into the agent's home skills dir (~/.bob/skills)
  --agent NAME  Force one agent: bob | devin | claude | cursor
  --dir DIR     Install into DIR directly (overrides scope detection)
  --uninstall   Remove the three skills from the target(s)
  -h, --help    Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --project|-p)  SCOPE="project" ;;
        --global|-g)   SCOPE="global" ;;
        --agent)       AGENT="$2"; shift ;;
        --dir)         TARGET_DIR="$2"; shift ;;
        --uninstall)   UNINSTALL=1 ;;
        -h|--help)     usage; exit 0 ;;
        *) echo "install.sh: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
    shift
done

# Map an agent name to its config dir. $1=name $2=scope.
agent_dir() {
    case "$1:$2" in
        bob:project)     echo ".bob" ;;
        devin:project)   echo ".devin" ;;
        claude:project)  echo ".claude" ;;
        cursor:project)  echo ".cursor" ;;
        bob:global)      echo "$HOME/.bob" ;;
        devin:global)    echo "$HOME/.config/devin" ;;
        claude:global)   echo "$HOME/.claude" ;;
        cursor:global)   echo "$HOME/.cursor" ;;
        *) return 1 ;;
    esac
}

# --- resolve the source tree ---------------------------------------------
# Local: this script sits inside bobdevkit/ after a clone.
# Remote: piped via curl — download the tarball and unpack to a temp dir.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0" 2>/dev/null)" 2>/dev/null && pwd || true)

if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/bob-pr" ]; then
    SRC="$SCRIPT_DIR"
else
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    TARBALL_URL="https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH"
    echo "Downloading bobdevkit from github.com/$REPO@$BRANCH"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$TARBALL_URL" | tar -xz -C "$TMP"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "$TARBALL_URL" | tar -xz -C "$TMP"
    else
        echo "install.sh: need curl or wget to download the package" >&2
        exit 1
    fi
    SRC="$TMP/ibmbob-hackathon-$BRANCH/bobdevkit"
    [ -d "$SRC" ] || { echo "install.sh: package missing in tarball" >&2; exit 1; }
fi

for s in $SKILLS; do
    [ -f "$SRC/$s/SKILL.md" ] || {
        echo "install.sh: $s/SKILL.md not found in source" >&2; exit 1; }
done

# --- resolve the target skills dirs --------------------------------------
TARGETS=""
if [ -n "$TARGET_DIR" ]; then
    TARGETS="$TARGET_DIR"
elif [ -n "$AGENT" ]; then
    BASE=$(agent_dir "$AGENT" "$SCOPE") || {
        echo "install.sh: unknown agent '$AGENT' (bob|devin|claude|cursor)" >&2
        exit 1; }
    TARGETS="$BASE/$SKILL_DIR_NAME"
elif [ "$SCOPE" = "global" ]; then
    TARGETS="$HOME/.bob/$SKILL_DIR_NAME"
else
    for cfg in .bob .devin .claude .cursor; do
        [ -d "$cfg" ] && TARGETS="$TARGETS $cfg/$SKILL_DIR_NAME"
    done
    if [ -z "$TARGETS" ]; then
        TARGETS=".bob/$SKILL_DIR_NAME"
        echo "No agent config dir found — defaulting to .bob/skills"
    fi
fi

# --- install / uninstall --------------------------------------------------
for target in $TARGETS; do
    if [ "$UNINSTALL" = 1 ]; then
        for s in $SKILLS; do
            rm -rf "$target/$s" && echo "Removed $s from $target/$s"
        done
        continue
    fi
    mkdir -p "$target"
    for s in $SKILLS; do
        rm -rf "$target/$s"
        cp -R "$SRC/$s" "$target/$s"
        find "$target/$s" -name __pycache__ -o -name '*.pyc' | while read -r f; do
            rm -rf "$f"
        done
        echo "Installed $s into $target/$s"
    done
done
