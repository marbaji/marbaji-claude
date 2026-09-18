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
#   commit-principles.sh            commit, push, open the PR, merge it (squash), reconcile
#   commit-principles.sh --dry-run  say what would happen, touch nothing
#
# Design (after the 2026-09-17 fresh-context review): the shared checkout is never switched to
# another branch. The commit is made in a detached temporary worktree cut from origin/<default>,
# so it works whatever branch the checkout is on, cannot carry unpushed local commits, and cannot
# collide with another live session's commit. The working file is left exactly as it was until the
# PR is merged, so the rule stays loaded through every failure; on success the file is restored to
# the merged content (identical text, now clean) and a checkout on <default> fast-forwards.
# "Clean" means identical to origin/<default>, so an edit merged by an earlier run stops counting.
#
# Since 2026-09-18 the SessionStart and SessionEnd hooks run this unattended (through
# principles-autocommit.sh), possibly from two sessions at once, so two guards:
#   - a lock directory, stale after 15 minutes, so concurrent runs do not both commit;
#   - a restore guard: the working file is hashed when copied into the worktree and again before
#     the restore; a file that changed in between (a session writing a rule mid-run) is left alone,
#     still dirty, and the next run commits the newer text.
#   Both are mkdir/hash checks, not flock: a write landing in the few ms between the final hash and
#   the restore, or two runs breaking one stale lock together, can still race. Accepted: the loser
#   loses gracefully (mkdir) or the next run recommits (hash).
#   - and no second cycle while an earlier run's principles/* branch exists on origin (an open PR
#     whose merge failed, or a run killed after its push): unattended runs must not pile up PRs.
# PRINCIPLES_FILE overrides the file (default ~/.claude/work-principles.md);
# COMMIT_PRINCIPLES_STATE the lock's folder (default ~/.claude/state).
set -u
FILE="${PRINCIPLES_FILE:-$HOME/.claude/work-principles.md}"
STATE="${COMMIT_PRINCIPLES_STATE:-$HOME/.claude/state}"
LOCK="$STATE/commit-principles.lock"
LOCK_STALE_S=900
DRY=""; [ "${1:-}" = "--dry-run" ] && DRY=1

target="$(readlink -f "$FILE" 2>/dev/null || true)"
[ -n "$target" ] && [ -f "$target" ] || { echo "commit-principles: $FILE does not resolve to a file"; exit 2; }
repo="$(git -C "$(dirname "$target")" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$repo" ] || { echo "commit-principles: $target is not inside a git repo; nothing to commit"; exit 0; }
rel="${target#"$repo"/}"
default="$(git -C "$repo" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
[ -n "$default" ] || default=main

# Compare against origin/<default>, refreshed: an edit merged by an earlier run is clean.
if ! git -C "$repo" fetch -q origin "$default" 2>/dev/null; then
    echo "commit-principles: could not fetch origin/$default (offline?); nothing committed, the edit stays in place and the next hook run retries."
    exit 1
fi
if git -C "$repo" diff --quiet "origin/$default" -- "$rel"; then
    exit 0   # identical to what is merged: the common case, say nothing
fi
leftover="$(git -C "$repo" ls-remote --heads origin 'principles/*' 2>/dev/null | awk '{print $2}' | sed 's|refs/heads/||' | head -3 | tr '\n' ' ')"
if [ -n "$leftover" ]; then
    echo "commit-principles: an earlier run left ${leftover}on origin (an open PR whose merge failed, or a run that died after pushing). Not opening another PR: merge or delete it (gh pr list --head <branch>; git push origin --delete <branch>), then this runs again."
    exit 1
fi
added=$(git -C "$repo" diff --numstat "origin/$default" -- "$rel" | awk '{print $1}')
removed=$(git -C "$repo" diff --numstat "origin/$default" -- "$rel" | awk '{print $2}')
branch="principles/$(date +%Y%m%d-%H%M%S)"
subject="principles: $(date +%Y-%m-%d) session rule(s) (+${added:-0}/-${removed:-0} lines)"

if [ -n "$DRY" ]; then
    echo "commit-principles [dry-run]: $rel differs from origin/$default (+${added:-0}/-${removed:-0})."
    echo "  would: worktree from origin/$default, commit --only $rel as \"$subject\" on $branch, push,"
    echo "  open a PR, squash-merge it, then restore $rel from origin/$default and fast-forward if on $default."
    exit 0
fi

mkdir -p "$STATE"
if ! mkdir "$LOCK" 2>/dev/null; then
    # mkdir is atomic, so whoever made the directory owns the run. A lock older than
    # LOCK_STALE_S is a run that died without cleaning up; break it and take over.
    # GNU stat first: BSD stat rejects -c cleanly (stderr only), while GNU stat reads -f as
    # "filesystem status" and prints a report to STDOUT before failing, which would poison $(( )).
    lock_mtime="$(stat -c %Y "$LOCK" 2>/dev/null || stat -f %m "$LOCK" 2>/dev/null || echo 0)"
    lock_age=$(( $(date +%s) - lock_mtime ))
    if [ "$lock_age" -gt "$LOCK_STALE_S" ] && rmdir "$LOCK" 2>/dev/null && mkdir "$LOCK" 2>/dev/null; then
        echo "commit-principles: broke a stale lock (${lock_age}s old)"
    else
        echo "commit-principles: another run holds the lock ($LOCK, ${lock_age}s old); nothing committed"
        exit 1
    fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

tmp="$(mktemp -d "${TMPDIR:-/tmp}/commit-principles.XXXXXX")"
pushed=""
cleanup() {
    git -C "$repo" worktree remove --force "$tmp" >/dev/null 2>&1 || rm -rf "$tmp"
    git -C "$repo" branch -q -D "$branch" >/dev/null 2>&1 || true
}
fail() {   # $1 = message. The working file was never touched, so the rule is still loaded and the next hook run retries.
    echo "commit-principles: $1"
    [ -n "$pushed" ] && git -C "$repo" push -q origin --delete "$branch" >/dev/null 2>&1 || true
    cleanup
    exit 1
}

git -C "$repo" worktree prune 2>/dev/null || true   # a run killed mid-way leaves a registration behind
git -C "$repo" worktree add -q --detach "$tmp" "origin/$default" 2>/dev/null || fail "could not create a worktree from origin/$default"
cp "$target" "$tmp/$rel" || fail "could not copy $rel into the worktree"
copied_hash="$(git hash-object "$target")"   # what this run commits; compared before the restore
git -C "$tmp" switch -q -c "$branch" || fail "could not create branch $branch"
git -C "$tmp" commit -q --only "$rel" -m "$subject" -m "Routed by the obsidian-memory session-end ritual (Step 8a). The rule's text carries its own anchor." || fail "commit failed"
git -C "$tmp" push -q -u origin "$branch" 2>/dev/null || fail "push of $branch failed (offline, or credentials?)"
pushed=1

url="$(cd "$tmp" && gh pr create --head "$branch" --base "$default" --title "$subject" \
      --body "Principle edit routed at session end; the rule carries its own citation. Committed by commit-principles.sh so it does not sit uncommitted in the shared checkout." 2>/dev/null)" \
    || fail "gh pr create failed; remote branch $branch deleted"
echo "commit-principles: opened $url"

# GitHub computes mergeability asynchronously; an immediate merge can 405 once or twice.
merged=""
for attempt in 1 2 3 4; do
    if err="$(cd "$tmp" && gh pr merge "$url" --squash 2>&1)"; then merged=1; break; fi
    sleep 5
done
if [ -z "$merged" ]; then
    cleanup
    echo "commit-principles: merge failed after 4 attempts; the PR stays open: $url"
    echo "  gh said: $err"
    echo "  $rel keeps the edit. Later runs will NOT open a second PR while $branch exists on origin: merge or delete it."
    exit 1
fi
git -C "$repo" push -q origin --delete "$branch" >/dev/null 2>&1 || true
cleanup

# Reconcile the shared checkout: same text, now clean; fast-forward when on <default>.
git -C "$repo" fetch -q origin "$default" 2>/dev/null || true
if [ "$(git hash-object "$target")" != "$copied_hash" ]; then
    echo "commit-principles: merged $url, but $rel changed during the run (another session wrote a rule); not restoring it. The newer text stays in place and the next run commits it."
    exit 0
fi
if [ "$(git -C "$repo" branch --show-current)" = "$default" ]; then
    # git refuses to fast-forward over a modified file even when the text is identical, so put the
    # file back to HEAD for the instant of the merge; the merge itself brings the rule in.
    git -C "$repo" restore --source=HEAD -- "$rel" 2>/dev/null || true
    if ! err="$(git -C "$repo" merge -q --ff-only "origin/$default" 2>&1)"; then
        git -C "$repo" restore --source="origin/$default" -- "$rel" 2>/dev/null || true
        echo "commit-principles: merged, but $default could not fast-forward (the rule is back in $rel): $err"
    fi
else
    git -C "$repo" restore --source="origin/$default" -- "$rel" 2>/dev/null \
        || echo "commit-principles: merged, but could not restore $rel from origin/$default; the working copy still holds the rule."
fi
echo "commit-principles: merged $url; $rel now matches origin/$default"
