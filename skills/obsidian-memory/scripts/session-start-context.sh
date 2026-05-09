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

# Current focus — the dashboard
CURRENT_FOCUS="$VAULT_PATH/Context/current-focus.md"
if [[ -f "$CURRENT_FOCUS" ]]; then
    echo "### Current focus"
    echo ""
    cat "$CURRENT_FOCUS"
    echo ""
fi

# Project backlog — read-only, user-maintained
BACKLOG="$VAULT_PATH/Context/Project Backlog.md"
if [[ -f "$BACKLOG" ]]; then
    echo "### Project backlog (read-only, user-maintained)"
    echo ""
    head -50 "$BACKLOG"
    BACKLOG_LINES=$(wc -l < "$BACKLOG" | tr -d ' ')
    if [[ "$BACKLOG_LINES" -gt 50 ]]; then
        echo ""
        echo "_(truncated; full file is $BACKLOG_LINES lines — read via \`obsidian read file=\"Context/Project Backlog\" vault=\"$VAULT_NAME\"\` if needed)_"
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
        echo "- _($((PROJECT_COUNT - 20)) more — see Work/$ORG_NAME/Projects/)_"
    fi
    echo ""
fi

# Git activity in current working directory if it's a repo
if git -C "$PWD" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    REPO_NAME="$(basename "$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null)")"
    BRANCH="$(git -C "$PWD" branch --show-current 2>/dev/null || echo '(detached)')"
    echo "### Git: $REPO_NAME @ $BRANCH"
    echo ""
    echo "**Recent commits:**"
    echo ""
    echo '```'
    git -C "$PWD" log --oneline -10 2>/dev/null
    echo '```'
    echo ""
    DIRTY=$(git -C "$PWD" status --short 2>/dev/null | head -10)
    if [[ -n "$DIRTY" ]]; then
        echo "**Working tree changes:**"
        echo ""
        echo '```'
        echo "$DIRTY"
        echo '```'
        echo ""
    fi
fi

# Operating reminders
echo "### Reminders"
echo ""
echo "- Session-start ritual: this hook supplies the read-context part. Run the 7-day vault lint (step 7 of \`skills/obsidian-memory/references/session-start.md\`) when due, but skip the context-reading steps (1-5)."
echo "- Session-end ritual: read \`skills/obsidian-memory/references/session-end.md\` when the user says \"done\", \"exit\", \"wrap up\", etc."
echo "- Retrieval rule: extract from the index, don't traverse via LLM. Prefer \`mcp__qmd__query\` (semantic) if registered; fall back to \`obsidian search:context\` (BM25) otherwise. Read whole files only when editing them."
echo "- File writes: \`~\` does not expand for the Write tool. Use the resolved absolute path \`$VAULT_PATH/...\`."
