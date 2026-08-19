#!/bin/bash
# PreToolUse gate: force an explicit opt-in the first time a usage window is
# fully consumed (extra-usage billing territory). Reads the rate-limit snapshot
# that ~/.claude/statusline.sh writes on every render. Asked ONCE per window:
# approving a tool call records an ack (see extra-usage-ack.sh), denying stops
# the work so you can /model down, /usage-credits, or wait for the reset.
# Fails OPEN on missing/stale data (API-key sessions have no rate_limits).

state="$HOME/.claude/usage-state.json"
ackdir="$HOME/.claude/usage-state-acks"
[ -f "$state" ] || exit 0

now=$(date +%s)
updated=$(jq -r '.updated_at // 0' "$state" 2>/dev/null) || exit 0
case "$updated" in ''|*[!0-9]*) exit 0;; esac
# Snapshot older than 6h → a different day's data; don't gate on it.
[ $(( now - updated )) -gt 21600 ] && exit 0

mkdir -p "$ackdir"
# Drop acks for windows that have long since reset.
find "$ackdir" -type f -mtime +8 -delete 2>/dev/null

check_window() { # $1=json key  $2=human label
    local pct resets ack reset_h
    pct=$(jq -r ".rate_limits.$1.used_percentage // 0" "$state" 2>/dev/null)
    resets=$(jq -r ".rate_limits.$1.resets_at // 0" "$state" 2>/dev/null)
    pct=$(printf '%.0f' "$pct" 2>/dev/null) || return 1
    case "$resets" in ''|*[!0-9]*) return 1;; esac
    [ "$pct" -ge 100 ] || return 1
    [ "$resets" -gt "$now" ] || return 1   # window already reset
    ack="$ackdir/$1-$resets"
    [ -f "$ack" ] && return 1              # already opted in for this window
    reset_h=$(date -r "$resets" +"%-I:%M %p %-m/%-d" 2>/dev/null || echo "the reset")
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"⚠️ EXTRA USAGE GATE: your %s usage window is 100%% consumed — continuing bills extra usage credits. APPROVE = opt in for this window (you will not be asked again until it resets at %s). DENY = stop here: /model to switch models, /usage-credits to manage extra usage, or wait for the reset."}}' "$2" "$reset_h"
    return 0
}

check_window five_hour "5-hour" && exit 0
check_window seven_day "7-day" && exit 0
exit 0
