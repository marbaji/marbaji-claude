#!/usr/bin/env bash
# obsidian-memory SessionStart hook
#
# Emits structured context at session start so the agent does not have to
# re-read SKILL.md, current-focus, recent sessions, etc. via LLM tokens.
# Target: ~2K tokens vs ~15-20K when the agent reads each file itself.
#
# Wire-up: add to ~/.claude/settings.json under hooks.SessionStart.
# See references/adopting-this-skill.md for the snippet.

set -uo pipefail

VAULT_NAME_FILE="$HOME/.claude/obsidian-vault-name"

if [[ ! -f "$VAULT_NAME_FILE" ]]; then
    # Skill not configured yet; emit nothing so the hook is a no-op.
    exit 0
fi

VAULT_NAME="$(head -1 "$VAULT_NAME_FILE" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
VAULT_PATH="$HOME/Documents/$VAULT_NAME"

if [[ ! -d "$VAULT_PATH" ]]; then
    # Vault path missing (new machine, renamed vault). Do not block session.
    echo "[obsidian-memory hook] Vault path \"$VAULT_PATH\" not found; skipping context injection." >&2
    exit 0
fi

# ---------- Output ----------

echo "## obsidian-memory session-start context"
echo ""
echo "Vault: \`$VAULT_NAME\`"
echo "Vault path: \`$VAULT_PATH\`"
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
PROJECTS_DIR="$VAULT_PATH/Work/Chalktalk/Projects"
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
        echo "- _($((PROJECT_COUNT - 20)) more — see Work/Chalktalk/Projects/)_"
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
echo "- Session-start ritual: read \`skills/obsidian-memory/references/session-start.md\` if you need to read project docs in detail."
echo "- Session-end ritual: read \`skills/obsidian-memory/references/session-end.md\` when the user says \"done\", \"exit\", \"wrap up\", etc."
echo "- Retrieval rule: extract from the index, don't traverse via LLM. Prefer \`obsidian search:context\` over reading whole files."
echo "- File writes: \`~\` does not expand for the Write tool. Use the resolved absolute path \`$VAULT_PATH/...\`."
