#!/bin/bash
# commit-principles.sh — commit and merge an edit to the principles file as its own PR.
#
# The session-end ritual routes cross-project habit lessons into ~/.claude/work-principles.md.
# That file is a symlink into a git repo, and the symlink makes the edit LOAD in every session
# whether or not it is committed, so nothing ever forced the commit: on 2026-09-17 three sessions
# had each written a rule and all three sat as one dirty working-tree diff (and 2026-09-15's PR
# #80 in that repo was the same cleanup, two days earlier). This script is the commit step the
# ritual lacked. Step 8 of references/session-end.md calls it right after writing the rule.
#
#   commit-principles.sh            commit, push, open the PR, merge it (squash), pull main
#   commit-principles.sh --dry-run  say what would happen, touch nothing
#
# Silent exit 0 when the file has no uncommitted change. Refuses (exit 2) when the repo checkout
# is on a branch other than its default: the edit then belongs in that branch's own PR, and a
# branch cut from a feature branch would drag the feature commits into the principles PR.
# PRINCIPLES_FILE overrides the file (default ~/.claude/work-principles.md).
set -u
FILE="${PRINCIPLES_FILE:-$HOME/.claude/work-principles.md}"
DRY=""; [ "${1:-}" = "--dry-run" ] && DRY=1

target="$(readlink -f "$FILE" 2>/dev/null || true)"
[ -n "$target" ] && [ -f "$target" ] || { echo "commit-principles: $FILE does not resolve to a file"; exit 2; }
repo="$(git -C "$(dirname "$target")" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$repo" ] || { echo "commit-principles: $target is not inside a git repo; nothing to commit"; exit 0; }
rel="${target#"$repo"/}"

if git -C "$repo" diff --quiet -- "$rel" && git -C "$repo" diff --quiet --cached -- "$rel"; then
    exit 0   # clean: the common case, say nothing
fi

default="$(git -C "$repo" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
[ -n "$default" ] || default=main
current="$(git -C "$repo" branch --show-current)"
added=$(git -C "$repo" diff --numstat -- "$rel" | awk '{print $1}')
removed=$(git -C "$repo" diff --numstat -- "$rel" | awk '{print $2}')

if [ "$current" != "$default" ]; then
    echo "commit-principles: $rel has uncommitted edits (+${added:-0}/-${removed:-0}) but the checkout"
    echo "  $repo is on '$current', not '$default'. Commit the edit into that branch's own PR"
    echo "  (git commit --only $rel) or switch the checkout to $default first."
    exit 2
fi

branch="principles/$(date +%Y%m%d-%H%M%S)"
subject="principles: $(date +%Y-%m-%d) session rule(s) (+${added:-0}/-${removed:-0} lines)"
if [ -n "$DRY" ]; then
    echo "commit-principles [dry-run]: would branch $branch from $default in $repo,"
    echo "  commit --only $rel as \"$subject\", push, open a PR, squash-merge it, pull $default."
    exit 0
fi

set -e
cd "$repo"
git switch -c "$branch" >/dev/null
git commit --only "$rel" -q -m "$subject" -m "Routed by the obsidian-memory session-end ritual (Step 8). The rule's text carries its own anchor."
git push -q -u origin "$branch"
url=$(gh pr create --fill --body "Principle edit routed at session end; the rule carries its own citation. Committed by commit-principles.sh so it does not sit uncommitted in the shared checkout." 2>&1 | tail -1)
echo "commit-principles: opened $url"
if gh pr merge "$branch" --squash --delete-branch >/dev/null 2>&1; then
    echo "commit-principles: merged and branch deleted"
else
    echo "commit-principles: merge deferred (checks pending or protection); PR stays open: $url"
    git switch "$default" >/dev/null
    exit 0
fi
git switch "$default" >/dev/null
git pull -q --ff-only
echo "commit-principles: $default now at $(git rev-parse --short HEAD); $rel clean"
