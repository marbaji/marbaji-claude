#!/bin/bash
# Claude Code statusline — powerline line 1 + claude-hud engine for detail lines.
#
# Line 1 (this script): explicitly-labeled identity segments (Model / Dir / Repo /
#   Branch / WT), an extra-usage alarm segment, and the clock.
# Lines 2+ (claude-hud, MIT, https://github.com/jarrodwatts/claude-hud):
#   Context bar, 5h + 7d usage with reset countdowns, tools/agents/todos activity.
# Side effect: writes ~/.claude/usage-state.json (rate-limit snapshot) that the
#   extra-usage-gate PreToolUse hook reads to force an opt-in prompt on overage.
# Reset-countdown formatting ported from claude-hud src/render/format-reset-time.ts.

input=$(cat)

# Validate JSON
if ! echo "$input" | jq -e . >/dev/null 2>&1; then
    echo "⚠ invalid input"
    exit 0
fi

# ---------- extract fields ----------
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
dir_name=$(basename "$cwd" 2>/dev/null || echo "?")
model_name=$(echo "$input" | jq -r '.model.display_name // .model.id // "Claude"' | sed 's/^claude-//' | cut -c1-20)
repo_full=$(echo "$input" | jq -r '.workspace.repo | if . then .owner + "/" + .name else empty end' 2>/dev/null)
worktree=$(echo "$input" | jq -r '.workspace.git_worktree // empty' 2>/dev/null)

# ---------- persist rate-limit snapshot for the extra-usage gate hook ----------
state_file="$HOME/.claude/usage-state.json"
if echo "$input" | jq -e '.rate_limits.five_hour // .rate_limits.seven_day' >/dev/null 2>&1; then
    echo "$input" | jq --arg ts "$(date +%s)" \
        '{updated_at: ($ts|tonumber), session_id: (.session_id // ""), rate_limits: .rate_limits}' \
        > "${state_file}.tmp" 2>/dev/null && mv "${state_file}.tmp" "$state_file" && chmod 600 "$state_file"
fi

# ---------- colors ----------
RESET=$'\033[0m'
BG_BLUE=$'\033[44m';    FG_BLUE=$'\033[34m'
BG_GREEN=$'\033[42m';   FG_GREEN=$'\033[32m'
BG_YELLOW=$'\033[43m';  FG_YELLOW=$'\033[33m'
BG_RED=$'\033[41m';     FG_RED=$'\033[31m'
BG_ORANGE=$'\033[48;5;208m'; FG_ORANGE=$'\033[38;5;208m'
BG_MAGENTA=$'\033[45m'; FG_MAGENTA=$'\033[35m'
BG_LTBLUE=$'\033[48;5;75m'; FG_LTBLUE=$'\033[38;5;75m'
FG_BLACK=$'\033[30m'
BOLD=$'\033[1m'; NOBOLD=$'\033[22m'
DIM=$'\033[2m';  NODIM=$'\033[22m'
BLINK=$'\033[5m'
SEP=''

# ---------- powerline segment builder ----------
out=""
prev_fg=""
seg_first=1
add_seg() { # $1=bg  $2=fg-matching-bg  $3=content
    if [ "$seg_first" -eq 1 ]; then
        out+="${1}${FG_BLACK} ${3} "
        seg_first=0
    else
        out+="${prev_fg}${1}${SEP}${FG_BLACK} ${3} "
    fi
    prev_fg="$2"
}

# ---------- git status (for model color + branch segment) ----------
branch=""; git_status=""
model_bg=$BG_GREEN; model_fg=$FG_GREEN
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
    [ -z "$branch" ] && branch=$(git -C "$cwd" rev-parse --short HEAD 2>/dev/null)

    status=$(git -C "$cwd" status --porcelain 2>/dev/null)
    staged=$(echo "$status" | grep -c '^[MADRC]' || true)
    modified=$(echo "$status" | grep -c '^.[MD]' || true)
    conflicts=$(echo "$status" | grep -c '^[UDA][UDA]' || true)
    ahead=$(git -C "$cwd" rev-list --count @{u}..HEAD 2>/dev/null || echo 0)
    behind=$(git -C "$cwd" rev-list --count HEAD..@{u} 2>/dev/null || echo 0)

    [ "$ahead" -gt 0 ] 2>/dev/null && git_status+=" ⇡$ahead"
    [ "$behind" -gt 0 ] 2>/dev/null && git_status+=" ⇣$behind"
    [ "$conflicts" -gt 0 ] && git_status+=" ~$conflicts"
    [ "$staged" -gt 0 ] && git_status+=" +$staged"
    [ "$modified" -gt 0 ] && git_status+=" !$modified"

    if [ -n "$git_status" ]; then
        model_bg=$BG_YELLOW; model_fg=$FG_YELLOW
    fi
fi

# ---------- rate-limit numbers ----------
now=$(date +%s)
pct5=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
pct7=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
resets5=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // 0')
resets7=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // 0')
[ -n "$pct5" ] && pct5=$(printf '%.0f' "$pct5" 2>/dev/null) || pct5=""
[ -n "$pct7" ] && pct7=$(printf '%.0f' "$pct7" 2>/dev/null) || pct7=""

# Relative countdown, ported from claude-hud format-reset-time.ts (MIT)
rel_time() {
    local diff mins hours days rem
    diff=$(( $1 - now ))
    if [ "$diff" -le 0 ]; then echo "now"; return; fi
    mins=$(( (diff + 59) / 60 ))
    if [ "$mins" -lt 60 ]; then echo "${mins}m"; return; fi
    hours=$(( mins / 60 )); rem=$(( mins % 60 ))
    if [ "$hours" -ge 24 ]; then
        days=$(( hours / 24 )); rem=$(( hours % 24 ))
        if [ "$rem" -gt 0 ]; then echo "${days}d ${rem}h"; else echo "${days}d"; fi
        return
    fi
    if [ "$rem" -gt 0 ]; then echo "${hours}h ${rem}m"; else echo "${hours}h"; fi
}

# ---------- build line 1 ----------
add_seg "$model_bg" "$model_fg" "${DIM}Model${NODIM} ${BOLD}${model_name}${NOBOLD}"
# Agent context (present when the session runs a named agent)
agent_name=$(echo "$input" | jq -r '.agent.name // empty' 2>/dev/null)
[ -n "$agent_name" ] && add_seg "$BG_MAGENTA" "$FG_MAGENTA" "${DIM}Agent${NODIM} ${agent_name}"
add_seg "$BG_BLUE" "$FG_BLUE" "${DIM}Dir${NODIM} ${dir_name}"
[ -n "$repo_full" ] && add_seg "$BG_MAGENTA" "$FG_MAGENTA" "${DIM}Repo${NODIM} ${repo_full}"
[ -n "$branch" ] && add_seg "$BG_LTBLUE" "$FG_LTBLUE" "${DIM}Branch${NODIM} ${branch}${git_status}"
[ -n "$worktree" ] && add_seg "$BG_MAGENTA" "$FG_MAGENTA" "${DIM}WT${NODIM} ${worktree}"

# Extra-usage alarm / near-limit warning segment
if [ -n "$pct5" ] && [ "$pct5" -ge 100 ] 2>/dev/null; then
    add_seg "$BG_RED" "$FG_RED" "${BLINK}⚠ EXTRA USAGE${RESET}${BG_RED}${FG_BLACK} 5h resets $(rel_time "$resets5")"
elif [ -n "$pct7" ] && [ "$pct7" -ge 100 ] 2>/dev/null; then
    add_seg "$BG_RED" "$FG_RED" "${BLINK}⚠ EXTRA USAGE${RESET}${BG_RED}${FG_BLACK} 7d resets $(rel_time "$resets7")"
elif [ -n "$pct5" ] && [ "$pct5" -ge 90 ] 2>/dev/null; then
    add_seg "$BG_ORANGE" "$FG_ORANGE" "◔ 5h ${pct5}% · resets in $(rel_time "$resets5")"
elif [ -n "$pct7" ] && [ "$pct7" -ge 90 ] 2>/dev/null; then
    add_seg "$BG_ORANGE" "$FG_ORANGE" "◔ 7d ${pct7}%"
fi

out+="${RESET}${prev_fg}${SEP}${RESET} $(date +"%Y/%m/%d %H:%M")"
printf '%s' "$out"

# ---------- keep the Fable/extra-usage snapshot fresh (background, never blocks) ----------
snap="$HOME/.claude/usage-external.json"
snap_age=999999
[ -f "$snap" ] && snap_age=$(( $(date +%s) - $(stat -f %m "$snap" 2>/dev/null || echo 0) ))
if [ "$snap_age" -gt 300 ]; then
    lock="$HOME/.claude/.usage-fetch.lock"
    # stale-lock cleanup (a fetch never takes 2 min)
    if [ -d "$lock" ] && [ $(( $(date +%s) - $(stat -f %m "$lock" 2>/dev/null || echo 0) )) -gt 120 ]; then rmdir "$lock" 2>/dev/null; fi
    if mkdir "$lock" 2>/dev/null; then
        ( "$HOME/.claude/scripts/fetch-usage-snapshot.sh"; rmdir "$lock" ) >/dev/null 2>&1 &
    fi
fi

# ---------- lines 2+: claude-hud (context bar, usage windows, activity) ----------
hud_js=$(ls -d "$HOME/.claude/plugins/cache/claude-hud/claude-hud"/*/dist/index.js 2>/dev/null | sort -V | tail -1)
if [ -n "$hud_js" ] && command -v node >/dev/null 2>&1; then
    hud_out=$(printf '%s' "$input" | node "$hud_js" 2>/dev/null | sed -E \
        -e 's/Jan ([0-9]{1,2})/1\/\1/g'  -e 's/Feb ([0-9]{1,2})/2\/\1/g' \
        -e 's/Mar ([0-9]{1,2})/3\/\1/g'  -e 's/Apr ([0-9]{1,2})/4\/\1/g' \
        -e 's/May ([0-9]{1,2})/5\/\1/g'  -e 's/Jun ([0-9]{1,2})/6\/\1/g' \
        -e 's/Jul ([0-9]{1,2})/7\/\1/g'  -e 's/Aug ([0-9]{1,2})/8\/\1/g' \
        -e 's/Sep ([0-9]{1,2})/9\/\1/g'  -e 's/Oct ([0-9]{1,2})/10\/\1/g' \
        -e 's/Nov ([0-9]{1,2})/11\/\1/g' -e 's/Dec ([0-9]{1,2})/12\/\1/g')
    [ -n "$hud_out" ] && printf '\n%s' "$hud_out"
fi
