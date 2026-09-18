#!/bin/bash
# principles-autocommit.sh — the hook-side of commit-principles.sh.
#
# Called by the SessionStart hook (from session-start-context.sh, first thing in its output) and by
# a SessionEnd hook. Both places used to rely on a model: Step 8a of the session-end ritual, and a
# session-start warning that on 2026-09-18 sat at line 167 of a 14.5 KB hook output and was
# missed. This script needs no model. It does no network work itself: it compares the principles
# file against origin/<default> as the last fetch left it (~60 ms), and when the file differs it
# launches commit-principles.sh DETACHED (nohup, outside the hook's process and timeout), logging
# to COMMIT_PRINCIPLES_LOG (default ~/Library/Logs/obsidian-memory/commit-principles.log), and
# prints one line so the session knows. Silent when clean. Always exits 0: a hook must never
# block a session over this.
#
# PRINCIPLES_AUTOCOMMIT_SYNC=1 runs commit-principles.sh in the foreground instead (tests, or a
# human who wants to watch it). PRINCIPLES_FILE overrides the file.
set -u
FILE="${PRINCIPLES_FILE:-$HOME/.claude/work-principles.md}"
LOG="${COMMIT_PRINCIPLES_LOG:-$HOME/Library/Logs/obsidian-memory/commit-principles.log}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMIT="$HERE/commit-principles.sh"

target="$(readlink -f "$FILE" 2>/dev/null || true)"
[ -n "$target" ] && [ -f "$target" ] || exit 0
repo="$(git -C "$(dirname "$target")" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$repo" ] || exit 0
rel="${target#"$repo"/}"
default="$(git -C "$repo" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
ref="origin/${default:-main}"
git -C "$repo" rev-parse --verify --quiet "$ref^{commit}" >/dev/null 2>&1 || ref=HEAD
git -C "$repo" diff --quiet "$ref" -- "$rel" 2>/dev/null && exit 0   # clean: the common case

numstat="$(git -C "$repo" diff --numstat "$ref" -- "$rel" | awk '{print "+"$1"/-"$2}')"
mkdir -p "$(dirname "$LOG")"
if [ "${PRINCIPLES_AUTOCOMMIT_SYNC:-}" = "1" ]; then
    echo "principles: $rel differs from $ref ($numstat lines); committing it now (log: $LOG)"
    { echo "== $(date '+%Y-%m-%d %H:%M:%S') sync run"; "$COMMIT"; } 2>&1 | tee -a "$LOG"
    exit 0
fi
echo "principles: $rel differs from $ref ($numstat lines); commit-principles.sh launched in the background (log: $LOG)"
{ echo "== $(date '+%Y-%m-%d %H:%M:%S') hook run"; nohup "$COMMIT"; } >> "$LOG" 2>&1 < /dev/null &
disown 2>/dev/null || true
exit 0
