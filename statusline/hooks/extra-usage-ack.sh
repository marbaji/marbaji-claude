#!/bin/bash
# PostToolUse companion to extra-usage-gate.sh: a tool that RAN while a usage
# window was at 100% means the user approved the gate's ask — record the ack
# (keyed by window + reset time) so the gate asks once per window, not per call.

state="$HOME/.claude/usage-state.json"
ackdir="$HOME/.claude/usage-state-acks"
[ -f "$state" ] || exit 0

now=$(date +%s)
updated=$(jq -r '.updated_at // 0' "$state" 2>/dev/null) || exit 0
case "$updated" in ''|*[!0-9]*) exit 0;; esac
[ $(( now - updated )) -gt 21600 ] && exit 0

mkdir -p "$ackdir"
for w in five_hour seven_day; do
    pct=$(jq -r ".rate_limits.$w.used_percentage // 0" "$state" 2>/dev/null)
    resets=$(jq -r ".rate_limits.$w.resets_at // 0" "$state" 2>/dev/null)
    pct=$(printf '%.0f' "$pct" 2>/dev/null) || continue
    case "$resets" in ''|*[!0-9]*) continue;; esac
    if [ "$pct" -ge 100 ] && [ "$resets" -gt "$now" ]; then
        touch "$ackdir/$w-$resets"
    fi
done
exit 0
