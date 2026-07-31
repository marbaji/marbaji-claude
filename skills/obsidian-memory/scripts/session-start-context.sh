#!/usr/bin/env bash
# obsidian-memory SessionStart hook
#
# Emits structured context at session start so the agent does not have to
# re-read SKILL.md, current-focus, recent sessions, etc. via LLM tokens.
# Target: ~2K tokens vs ~15-20K when the agent reads each file itself.
#
# Wire-up: add to ~/.claude/settings.json under hooks.SessionStart.
# See references/adopting-this-skill.md for the snippet.
#
# Configuration files (in priority order):
#   ~/.claude/obsidian-vault-path   — full filesystem path to the vault (preferred)
#   ~/.claude/obsidian-vault-name   — vault folder name (legacy; resolves to $HOME/Documents/<NAME>)
#   ~/.claude/obsidian-org-name     — your org folder under Work/ (defaults to "Chalktalk" for back-compat)

set -uo pipefail

VAULT_PATH_FILE="$HOME/.claude/obsidian-vault-path"
VAULT_NAME_FILE="$HOME/.claude/obsidian-vault-name"
ORG_NAME_FILE="$HOME/.claude/obsidian-org-name"

# ---------- Resolve VAULT_PATH ----------

VAULT_PATH=""
VAULT_NAME=""

if [[ -f "$VAULT_PATH_FILE" ]]; then
    VAULT_PATH="$(head -1 "$VAULT_PATH_FILE" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
fi

if [[ -z "$VAULT_PATH" && -f "$VAULT_NAME_FILE" ]]; then
    # Legacy back-compat: derive path from name.
    VAULT_NAME="$(head -1 "$VAULT_NAME_FILE" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if [[ -n "$VAULT_NAME" ]]; then
        VAULT_PATH="$HOME/Documents/$VAULT_NAME"
    fi
fi

if [[ -z "$VAULT_PATH" ]]; then
    # Skill not configured (no path file, or name file blank). No-op.
    exit 0
fi

# Always derive VAULT_NAME from the resolved path so downstream uses are consistent.
VAULT_NAME="$(basename "$VAULT_PATH")"

if [[ ! -d "$VAULT_PATH" ]]; then
    # Vault path missing (new machine, renamed vault). Do not block session.
    echo "[obsidian-memory hook] Vault path \"$VAULT_PATH\" not found; skipping context injection." >&2
    exit 0
fi

# ---------- Resolve ORG_NAME ----------

ORG_NAME="Chalktalk"  # back-compat default for existing setups
if [[ -f "$ORG_NAME_FILE" ]]; then
    CONFIGURED_ORG="$(head -1 "$ORG_NAME_FILE" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if [[ -n "$CONFIGURED_ORG" ]]; then
        ORG_NAME="$CONFIGURED_ORG"
    fi
fi

# ---------- Output ----------

echo "## obsidian-memory session-start context"
echo ""
echo "Vault: \`$VAULT_NAME\`"
echo "Vault path: \`$VAULT_PATH\`"
echo "Org folder: \`$ORG_NAME\` (under Work/)"
echo ""

# Current focus — the dashboard. Emit ONLY the live sections.
#
# current-focus.md also carries `## Complete` and `## Retired Projects`, which
# accumulate finished work forever by design. An unbounded `cat` therefore grows
# without limit: on 2026-07-31 the file was 17,758 chars / 53 project entries, of
# which 40 were marked done (✅) or archived (🗄️) — 13,585 chars, 54% of this
# hook's entire output, injected into every single session. That blew the ~2K-token
# budget in this script's header by 3.1x.
#
# Stop at the first archival heading, and keep a hard byte ceiling as a backstop so
# the next growth spurt can't silently blow the budget again. Nothing is deleted
# from the vault: the history stays in the file, it just stops being injected.
CURRENT_FOCUS="$VAULT_PATH/Context/current-focus.md"
# Budget is in BYTES, and every measurement below is in bytes under LC_ALL=C.
# This matters: the vault is UTF-8 and these headings carry emoji status markers
# (✅ 🗄️) at 3-4 bytes each. An earlier draft cut with `head -c` (bytes) but
# decided whether to print the truncation notice with `${#VAR}` (characters).
# On emoji-heavy content those disagree — 5,399 chars measured 5,799 bytes in
# testing — so output could be truncated while the notice stayed silent, which
# is the exact failure the ceiling exists to surface. `head -c` can also split a
# multi-byte character mid-sequence. Truncating at a LINE boundary instead fixes
# both: never mid-character, and the notice fires iff bytes were actually dropped.
FOCUS_MAX_BYTES="${OBSIDIAN_MEMORY_FOCUS_MAX_BYTES:-8000}"
BACKLOG_MAX_BYTES="${OBSIDIAN_MEMORY_BACKLOG_MAX_BYTES:-4000}"

# Reject a malformed budget rather than silently emitting nothing. A non-numeric
# or non-positive value would make `awk -v max=...` compare against 0 and drop
# every line, with no warning; `set -u` can't catch it because the var IS set.
_validate_budget() {  # $1=name $2=value $3=default -> echoes a usable value
    case "$2" in
        '' | *[!0-9]*)
            printf '[obsidian-memory hook] %s=%s is not a positive integer; using %s.\n' \
                "$1" "$2" "$3" >&2
            printf '%s' "$3" ;;
        *)
            if [[ "$2" -le 0 ]]; then
                printf '[obsidian-memory hook] %s=%s must be > 0; using %s.\n' "$1" "$2" "$3" >&2
                printf '%s' "$3"
            else
                printf '%s' "$2"
            fi ;;
    esac
}
FOCUS_MAX_BYTES="$(_validate_budget OBSIDIAN_MEMORY_FOCUS_MAX_BYTES "$FOCUS_MAX_BYTES" 8000)"
BACKLOG_MAX_BYTES="$(_validate_budget OBSIDIAN_MEMORY_BACKLOG_MAX_BYTES "$BACKLOG_MAX_BYTES" 4000)"

# Emit at most $1 bytes of stdin, cut at a line boundary so a multi-byte
# character is never split. LC_ALL=C makes awk's length() count bytes.
_emit_capped() {  # $1=max-bytes ; stdin -> stdout
    LC_ALL=C awk -v max="$1" '{ n += length($0) + 1; if (n > max) exit; print }'
}

if [[ -f "$CURRENT_FOCUS" ]]; then
    echo "### Current focus"
    echo ""
    FOCUS_LIVE="$(awk '/^## (Complete|Retired Projects)/ { exit } { print }' "$CURRENT_FOCUS")"
    FOCUS_SHOWN="$(printf '%s\n' "$FOCUS_LIVE" | _emit_capped "$FOCUS_MAX_BYTES")"
    printf '%s\n' "$FOCUS_SHOWN"
    FOCUS_LIVE_BYTES="$(printf '%s' "$FOCUS_LIVE" | LC_ALL=C wc -c | tr -d ' ')"
    FOCUS_SHOWN_BYTES="$(printf '%s' "$FOCUS_SHOWN" | LC_ALL=C wc -c | tr -d ' ')"
    if [[ "$FOCUS_SHOWN_BYTES" -lt "$FOCUS_LIVE_BYTES" ]]; then
        printf '\n_(truncated at ~%s bytes of %s. Read `Context/current-focus.md` for the rest.)_\n' \
            "$FOCUS_MAX_BYTES" "$FOCUS_LIVE_BYTES"
    fi
    echo ""
    echo "_Completed and retired projects live in the same file under \`## Complete\` / \`## Retired Projects\`, deliberately not injected. Read the file if you need them._"
    echo ""
fi

# Project backlog (read-only, user-maintained).
# Bounded on BOTH lines and bytes: `head -50` alone caps line count but not size,
# so 50 pathologically long lines could blow the whole hook's budget.
BACKLOG="$VAULT_PATH/Context/Project Backlog.md"
if [[ -f "$BACKLOG" ]]; then
    echo "### Project backlog (read-only, user-maintained)"
    echo ""
    BACKLOG_HEAD="$(head -50 "$BACKLOG")"
    BACKLOG_SHOWN="$(printf '%s\n' "$BACKLOG_HEAD" | _emit_capped "$BACKLOG_MAX_BYTES")"
    printf '%s\n' "$BACKLOG_SHOWN"
    BACKLOG_LINES="$(wc -l < "$BACKLOG" | tr -d ' ')"
    BACKLOG_HEAD_BYTES="$(printf '%s' "$BACKLOG_HEAD" | LC_ALL=C wc -c | tr -d ' ')"
    BACKLOG_SHOWN_BYTES="$(printf '%s' "$BACKLOG_SHOWN" | LC_ALL=C wc -c | tr -d ' ')"
    if [[ "$BACKLOG_LINES" -gt 50 || "$BACKLOG_SHOWN_BYTES" -lt "$BACKLOG_HEAD_BYTES" ]]; then
        echo ""
        echo "_(truncated; full file is $BACKLOG_LINES lines. Read via \`obsidian read file=\"Context/Project Backlog\" vault=\"$VAULT_NAME\"\` if needed.)_"
    fi
    echo ""
fi

# Recent sessions — paths only, not content
SESSION_DIR="$VAULT_PATH/Sessions"
if [[ -d "$SESSION_DIR" ]]; then
    echo "### Recent sessions (last 5 by filename)"
    echo ""
    find "$SESSION_DIR" -name "*.md" -type f 2>/dev/null \
        | sort -r \
        | head -5 \
        | sed "s|$VAULT_PATH/||" \
        | awk '{print "- `" $0 "`"}'
    echo ""
    echo "_Read individually via \`obsidian read\` only when relevant to current work._"
    echo ""
fi

# Active projects — file listing only, not content
PROJECTS_DIR="$VAULT_PATH/Work/$ORG_NAME/Projects"
if [[ -d "$PROJECTS_DIR" ]]; then
    PROJECT_COUNT=$(find "$PROJECTS_DIR" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "### Work projects ($PROJECT_COUNT total)"
    echo ""
    find "$PROJECTS_DIR" -maxdepth 1 -name "*.md" -type f 2>/dev/null \
        | sort \
        | sed "s|$VAULT_PATH/||" \
        | awk '{print "- `" $0 "`"}' \
        | head -20
    if [[ "$PROJECT_COUNT" -gt 20 ]]; then
        echo "- _($((PROJECT_COUNT - 20)) more; see Work/$ORG_NAME/Projects/)_"
    fi
    echo ""
fi

# NO git section here — deliberately removed 2026-07-31 (was ~963 chars/session).
#
# Repo name, current branch, working-tree status, and recent commits are already in
# context twice over before this hook runs:
#   1. Claude Code injects its own `gitStatus` block into every session (branch, main
#      branch, status, recent commits). Always present, can't drift.
#   2. The separate `CHANGES=$(git status --porcelain ...)` SessionStart hook in
#      ~/.claude/settings.json reports the uncommitted-change count and repo name.
# A third copy bought nothing and cost a `git log` subprocess on the session-start
# critical path. If you need more git detail, ask for it — don't preload it.

# Operating reminders
echo "### Reminders"
echo ""
echo "- Session-start ritual: this hook supplies the read-context part. Run the 7-day vault lint (step 7 of \`skills/obsidian-memory/references/session-start.md\`) when due, but skip the context-reading steps (1-5)."
echo "- Session-end ritual: read \`skills/obsidian-memory/references/session-end.md\` when the user says \"done\", \"exit\", \"wrap up\", etc."
echo "- Retrieval rule: extract from the index, don't traverse via LLM. Prefer \`mcp__qmd__query\` (semantic) if registered; fall back to \`obsidian search:context\` (BM25) otherwise. Read whole files only when editing them."
echo "- File writes: \`~\` does not expand for the Write tool. Use the resolved absolute path \`$VAULT_PATH/...\`."
