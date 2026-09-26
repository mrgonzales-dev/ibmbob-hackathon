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

# --- mini TUI: arrow-key menus over /dev/tty ------------------------------
# Works under `curl | sh` because input comes from /dev/tty, not stdin.

TTY_OK=0
if [ "$INTERACTIVE" = 1 ] && [ -t 1 ] && [ -r /dev/tty ] && [ -w /dev/tty ]; then
    TTY_OK=1
fi

KEY=""
read_key() {
    hex=$(dd bs=1 count=1 < /dev/tty 2>/dev/null | od -An -tx1 | tr -d ' \n')
    case "$hex" in
        1b)
            seq=$(dd bs=1 count=2 < /dev/tty 2>/dev/null)
            case "$seq" in
                "[A") KEY=up ;;
                "[B") KEY=down ;;
                *)    KEY=esc ;;
            esac ;;
        20)    KEY=space ;;
        0d|0a) KEY=enter ;;
        03)    KEY=quit ;;
        71|51) KEY=q ;;
        *)     KEY=other ;;
    esac
}

STTY_SAVED=""
tui_on() {
    STTY_SAVED=$(stty -g < /dev/tty 2>/dev/null || true)
    stty -icanon -echo min 1 time 0 < /dev/tty 2>/dev/null || true
    printf '\033[?25l' > /dev/tty   # hide cursor
}
tui_off() {
    printf '\033[?25h' > /dev/tty   # show cursor
    [ -n "$STTY_SAVED" ] && stty "$STTY_SAVED" < /dev/tty 2>/dev/null || true
}

# menu <prompt> <one|multi> <opt> ... — sets MENU_PICK to 1-based indices.
menu() {
    _prompt=$1; _mode=$2; shift 2
    _n=$#
    _opts=""
    for opt in "$@"; do
        if [ -z "$_opts" ]; then _opts="$opt"; else _opts="$_opts
$opt"; fi
    done
    _sel=1
    # state string of 0/1 per option
    _state=""
    i=1
    while [ "$i" -le "$_n" ]; do
        [ "$_mode" = multi ] && _state="$_state 1" || _state="$_state 0"
        i=$((i + 1))
    done
    _state="${_state# }"

    tui_on
    trap 'tui_off' INT TERM
    printf '%s\n' "${BLUE}?${RESET} ${_prompt}" > /dev/tty
    _menu_draw
    while :; do
        read_key
        case "$KEY" in
            up)   _sel=$(( (_sel + _n - 2) % _n + 1 )) ;;
            down) _sel=$(( _sel % _n + 1 )) ;;
            space)
                if [ "$_mode" = multi ]; then
                    _new=""
                    i=1
                    for b in $_state; do
                        if [ "$i" = "$_sel" ]; then _new="$_new $((1 - b))"; else _new="$_new $b"; fi
                        i=$((i + 1))
                    done
                    _state="${_new# }"
                fi ;;
            enter)
                if [ "$_mode" = one ]; then
                    _new=""
                    i=1
                    for b in $_state; do
                        [ "$i" = "$_sel" ] && _new="$_new 1" || _new="$_new 0"
                        i=$((i + 1))
                    done
                    _state="${_new# }"
                fi
                break ;;
            quit|q)
                tui_off; printf '\n' > /dev/tty; exit 130 ;;
        esac
        printf '\033[%dA' "$_n" > /dev/tty   # back to first option line
        _menu_draw
    done
    tui_off
    trap - INT TERM

    MENU_PICK=""
    i=1
    for b in $_state; do
        [ "$b" = 1 ] && MENU_PICK="$MENU_PICK $i"
        i=$((i + 1))
    done
    MENU_PICK="${MENU_PICK# }"
}

_menu_draw() {
    i=1
    _ifs=$IFS
    IFS="$(printf '\nx')"; IFS=${IFS%x}
    for opt in $_opts; do
        checked=$(echo "$_state" | cut -d' ' -f"$i")
        if [ "$_mode" = multi ]; then
            [ "$checked" = 1 ] && box="[x]" || box="[ ]"
            pre="$box "
        else
            pre=""
        fi
        if [ "$i" = "$_sel" ]; then
            printf '\033[2K%s\n' "${CYAN}${BOLD}❯ ${pre}${opt}${RESET}" > /dev/tty
        else
            printf '\033[2K%s\n' "  ${pre}${opt}" > /dev/tty
        fi
        i=$((i + 1))
    done
    IFS=$_ifs
}

# Map picked indices back to items of a space-separated list.
pick_items() {
    out=""
    for n in $MENU_PICK; do
        i=1
        for item in $1; do
            [ "$i" = "$n" ] && out="$out $item"
            i=$((i + 1))
        done
    done
    echo "${out# }"
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
if [ "$TTY_OK" = 1 ] && [ "$UNINSTALL" = 0 ]; then
    menu "which skills? ${DIM}(space to toggle, enter to confirm)${RESET}" multi $ALL_SKILLS
    SKILLS=$(pick_items "$ALL_SKILLS")
    [ -z "$SKILLS" ] && { say "no skills picked — nothing to do"; exit 0; }
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
        step "  found:$(echo "${FOUND# }" | tr ' ' ',')"
        if [ "$TTY_OK" = 1 ]; then
            _nt=0
            for t in $TARGETS; do _nt=$((_nt + 1)); done
            menu "install into which? ${DIM}(enter to pick)${RESET}" one $TARGETS "all of the above"
            if [ "$MENU_PICK" != "$((_nt + 1))" ]; then
                TARGETS=$(pick_items "$TARGETS")
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
