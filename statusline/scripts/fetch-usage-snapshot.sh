#!/bin/bash
# Fable weekly + extra-usage feeder for the status line.
# Fetches the same unbilled usage metadata that /usage shows (GET /api/oauth/usage,
# OAuth token read from the macOS Keychain at runtime — never written to disk),
# and writes a claude-hud external snapshot (~/.claude/usage-external.json) with:
#   - model_scoped: per-model weekly windows (e.g. "Fable") absent from statusline stdin
#   - balance_label: extra-usage state, ALWAYS emitted when the account reports an
#     extra_usage block, so the status line never goes silent about it. Spending reads
#     "Extra $583.84 of $250"; every off state names its cause ("Extra OFF · out of
#     credits", "· turned off", "· $250 cap reached"), because a missing label used to
#     be indistinguishable from a broken feeder.
# claude-hud merges these alongside the live stdin windows (see its README,
# display.externalUsagePath). Zero tokens; network only to api.anthropic.com.
# Invoked by ~/.claude/statusline.sh when the snapshot is >5 min old.

out="$HOME/.claude/usage-external.json"

tok=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null \
      | jq -r '.claudeAiOauth.accessToken // empty')
[ -n "$tok" ] || exit 0

resp=$(curl -sS -m 15 "https://api.anthropic.com/api/oauth/usage" \
    -H "Authorization: Bearer $tok" \
    -H "anthropic-beta: oauth-2025-04-20" \
    -H "Content-Type: application/json" 2>/dev/null)
echo "$resp" | jq -e '.limits' >/dev/null 2>&1 || exit 0

echo "$resp" | jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
def money:
  (. * 100 | round) as $c
  | (($c / 100) | floor | tostring) + "."
  + (($c % 100) | tostring | if length == 1 then "0" + . else . end);

def dollars: floor | tostring;

{
  updated_at: $ts,
  model_scoped: [
    .limits[]?
    | select(.kind == "weekly_scoped" and .scope.model.display_name != null)
    | {
        display_name: .scope.model.display_name,
        utilization: .percent,
        resets_at: .resets_at
      }
  ]
}
+ ( (.extra_usage // null) as $e
    | if $e == null then {}
      else
        (($e.decimal_places // 2) as $dp | pow(10; $dp)) as $div
        | (($e.used_credits  // 0) / $div) as $used
        | (($e.monthly_limit // 0) / $div) as $cap
        | { balance_label:
            ( if $e.is_enabled == true then
                "Extra $" + ($used | money)
                + (if $cap > 0 then " of $" + ($cap | dollars) else "" end)
              elif $e.user_disabled == true then
                "Extra OFF \u00b7 turned off"
              elif $e.spend_limit_reached == true then
                "Extra OFF \u00b7 $" + ($cap | dollars) + " cap reached"
              elif ($e.disabled_reason // "") != "" then
                "Extra OFF \u00b7 " + ($e.disabled_reason | gsub("_"; " "))
              else
                "Extra OFF"
              end ) }
      end )
' > "${out}.tmp.$$" 2>/dev/null && [ -s "${out}.tmp.$$" ] && mv "${out}.tmp.$$" "$out" && chmod 600 "$out"
