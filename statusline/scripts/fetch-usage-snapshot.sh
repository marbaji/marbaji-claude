#!/bin/bash
# Fable weekly + extra-usage feeder for the status line.
# Fetches the same unbilled usage metadata that /usage shows (GET /api/oauth/usage,
# OAuth token read from the macOS Keychain at runtime — never written to disk),
# and writes a claude-hud external snapshot (~/.claude/usage-external.json) with:
#   - model_scoped: per-model weekly windows (e.g. "Fable") absent from statusline stdin
#   - balance_label: running extra-usage dollars, e.g. "Extra $583.84"
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
+ (if (.extra_usage.is_enabled == true and (.extra_usage.used_credits // 0) > 0) then
    { balance_label: ("Extra (Monthly) $" + ((.extra_usage.used_credits / pow(10; (.extra_usage.decimal_places // 2))) * 100 | round / 100 | tostring)) }
  else {} end)
' > "${out}.tmp.$$" 2>/dev/null && [ -s "${out}.tmp.$$" ] && mv "${out}.tmp.$$" "$out" && chmod 600 "$out"
