#!/bin/sh
# bobdevkit installer — installs the Bob devkit skills into an AI
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
ALL_SKILLS="bob-upgrade-check bob-impact bob-pr"
SKILL_DIR_NAME="skills"

SCOPE="project"
AGENT=""
TARGET_DIR=""
UNINSTALL=0
INTERACTIVE=1

usage() {
    cat <<'EOF'
Usage: install.sh [--project|--global] [--agent NAME] [--dir DIR] [--uninstall]

  --project     Install into detected agent config dirs in cwd (default)
  --global      Install into the agent's home skills dir (~/.bob/skills)
  --agent NAME  Force one agent: bob | devin | claude | cursor
  --dir DIR     Install into DIR directly (overrides scope detection)
  --uninstall   Remove the skills from the target(s)
  --yes         No prompts: install all skills into all detected dirs
  -h, --help    Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --project|-p)  SCOPE="project" ;;
        --global|-g)   SCOPE="global" ;;
        --agent)       [ $# -ge 2 ] || { echo "install.sh: --agent needs a name" >&2; exit 1; }
                       AGENT="$2"; shift ;;
        --dir)         [ $# -ge 2 ] || { echo "install.sh: --dir needs a path" >&2; exit 1; }
                       TARGET_DIR="$2"; shift ;;
        --uninstall)   UNINSTALL=1 ;;
        --yes|-y)      INTERACTIVE=0 ;;
        -h|--help)     usage; exit 0 ;;
        *) echo "install.sh: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
    shift
done

# --- colors ---------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD=$(printf '\033[1m');  DIM=$(printf '\033[2m')
    PURPLE=$(printf '\033[35m'); BLUE=$(printf '\033[34m')
    CYAN=$(printf '\033[36m');  GREEN=$(printf '\033[32m')
    RESET=$(printf '\033[0m')
else
    BOLD="" DIM="" PURPLE="" BLUE="" CYAN="" GREEN="" RESET=""
fi

say()  { printf '%s\n' "$*"; }
step() { printf '%s\n' "${DIM}$*${RESET}"; }
ok()   { printf '%s\n' "${GREEN}✓${RESET} $*"; }

banner() {
    [ -n "$BOLD" ] || return 0
    printf '%s\n' "${PURPLE}${BOLD}"
    cat <<'EOF'
██████╗  ██████╗ ██████╗     ██████╗ ███████╗██╗   ██╗██╗  ██╗██╗████████╗
██╔══██╗██╔═══██╗██╔══██╗    ██╔══██╗██╔════╝██║   ██║██║ ██╔╝██║╚══██╔══╝
██████╔╝██║   ██║██████╔╝    ██║  ██║█████╗  ██║   ██║█████╔╝ ██║   ██║   
██╔══██╗██║   ██║██╔══██╗    ██║  ██║██╔══╝  ╚██╗ ██╔╝██╔═██╗ ██║   ██║   
██████╔╝╚██████╔╝██████╔╝    ██████╔╝███████╗ ╚████╔╝ ██║  ██╗██║   ██║   
╚═════╝  ╚═════╝ ╚═════╝     ╚═════╝ ╚══════╝  ╚═══╝  ╚═╝  ╚═╝╚═╝   ╚═╝   
EOF
    printf '%s\n' "${RESET}${DIM}  terminal-native skills for your AI agent${RESET}"
    printf '\n'
}

# Map an agent name to its config dir. $1=name $2=scope.
agent_dir() {
    case "$1:$2" in
        bob:project)     echo ".bob" ;;
        devin:project)   echo ".devin" ;;
        claude:project)  echo ".claude" ;;
        cursor:project)  echo ".cursor" ;;
        windsurf:project) echo ".codeium/windsurf" ;;
        bob:global)      echo "$HOME/.bob" ;;
        devin:global)    echo "$HOME/.config/devin" ;;
        claude:global)   echo "$HOME/.claude" ;;
        cursor:global)   echo "$HOME/.cursor" ;;
        windsurf:global) echo "$HOME/.codeium/windsurf" ;;
        *) return 1 ;;
    esac
}

# Read one line from the controlling terminal (works under curl | sh).
ask() {
    printf '%s' "$1" > /dev/tty
    read -r answer < /dev/tty || answer=""
    echo "$answer"
}

# --- resolve the source tree ---------------------------------------------
banner

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0" 2>/dev/null)" 2>/dev/null && pwd || true)

if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/bob-pr" ]; then
    SRC="$SCRIPT_DIR"
else
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    TARBALL_URL="https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH"
    step "downloading bobdevkit from github.com/$REPO@$BRANCH"
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

# --- pick the skills -------------------------------------------------------
SKILLS="$ALL_SKILLS"
if [ "$INTERACTIVE" = 1 ] && [ -t 1 ] && [ -r /dev/tty ] && [ "$UNINSTALL" = 0 ]; then
    say "${BLUE}?${RESET} which skills? ${DIM}(numbers, space/comma separated — Enter for all)${RESET}"
    i=1
    for s in $ALL_SKILLS; do
        say "  ${PURPLE}$i)${RESET} $s"
        i=$((i + 1))
    done
    answer=$(ask "${BOLD}>${RESET} ")
    if [ -n "$answer" ]; then
        SKILLS=""
        # shellcheck disable=SC2086
        for n in $(echo "$answer" | tr ',' ' '); do
            i=1
            for s in $ALL_SKILLS; do
                [ "$i" = "$n" ] && SKILLS="$SKILLS $s"
                i=$((i + 1))
            done
        done
        SKILLS=$(echo "$SKILLS" | sed 's/^ *//')
        [ -z "$SKILLS" ] && { say "no skills picked — nothing to do"; exit 0; }
    fi
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
        echo "install.sh: unknown agent '$AGENT' (bob|devin|claude|cursor|windsurf)" >&2
        exit 1; }
    TARGETS="$BASE/$SKILL_DIR_NAME"
elif [ "$SCOPE" = "global" ]; then
    TARGETS="$HOME/.bob/$SKILL_DIR_NAME"
else
    FOUND=""
    for cfg in .bob .devin .claude .cursor .codeium/windsurf; do
        if [ -d "$cfg" ]; then
            FOUND="$FOUND $cfg"
            TARGETS="$TARGETS $cfg/$SKILL_DIR_NAME"
        fi
    done
    if [ -n "$FOUND" ]; then
        step "detecting agent environments…"
        step "  found:$(echo "$FOUND" | tr ' ' ',')"
        if [ "$INTERACTIVE" = 1 ] && [ -t 1 ] && [ -r /dev/tty ]; then
            say "${BLUE}?${RESET} install into which? ${DIM}(number — Enter for all detected)${RESET}"
            i=1
            for t in $TARGETS; do
                say "  ${PURPLE}$i)${RESET} $t"
                i=$((i + 1))
            done
            answer=$(ask "${BOLD}>${RESET} ")
            if [ -n "$answer" ]; then
                i=1; PICKED=""
                for t in $TARGETS; do
                    [ "$i" = "$answer" ] && PICKED="$t"
                    i=$((i + 1))
                done
                [ -n "$PICKED" ] && TARGETS="$PICKED"
            fi
        fi
    else
        TARGETS=".bob/$SKILL_DIR_NAME"
        step "no agent config dir found — defaulting to .bob/skills"
    fi
fi

# --- install / uninstall --------------------------------------------------
for target in $TARGETS; do
    if [ "$UNINSTALL" = 1 ]; then
        for s in $ALL_SKILLS; do
            if [ -d "$target/$s" ]; then
                rm -rf "$target/$s"
                ok "removed $s ${DIM}from $target/$s${RESET}"
            fi
        done
        continue
    fi
    mkdir -p "$target"
    step "installing into $target"
    for s in $SKILLS; do
        rm -rf "$target/$s"
        cp -R "$SRC/$s" "$target/$s"
        find "$target/$s" -name __pycache__ -o -name '*.pyc' | while read -r f; do
            rm -rf "$f"
        done
        ok "$s ${DIM}installed${RESET}"
    done
done

[ "$UNINSTALL" = 0 ] && { printf '\n'; ok "done — ${BOLD}restart your agent${RESET}"; }
