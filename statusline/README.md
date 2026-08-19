# Status line + extra-usage visibility

A two-layer Claude Code status line with an opt-in gate that fires when a usage window is
fully consumed. Built 2026-08-18; committed here 2026-08-19 so the live copies in `~/.claude`
stop being the only copy.

**Line 1** (`statusline.sh`) — labeled identity segments: Model, Agent, Dir, Repo, Branch
(with ahead/behind/staged/modified counts), worktree, an overage alarm segment, and the clock.

**Lines 2+** — [claude-hud](https://github.com/jarrodwatts/claude-hud) (MIT), invoked by
`statusline.sh` from the plugin cache: context bar, 5h/7d/per-model usage windows with reset
countdowns, and live tool/skill/agent/todo activity.

## Files

| File | Lives at | Role |
|---|---|---|
| `statusline.sh` | `~/.claude/statusline.sh` | Renders line 1, shells out to claude-hud for the rest, and writes the rate-limit snapshot the gate reads |
| `scripts/fetch-usage-snapshot.sh` | `~/.claude/scripts/` | Every ~5 min, pulls the unbilled OAuth usage endpoint for per-model weekly windows and month-to-date extra-usage dollars |
| `hooks/extra-usage-gate.sh` | `~/.claude/hooks/` | PreToolUse. At 100% of a window, forces one explicit approve/deny before work continues |
| `hooks/extra-usage-ack.sh` | `~/.claude/hooks/` | PostToolUse. Records the approval so the gate asks once per window, not once per tool call |
| `claude-hud.config.json` | `~/.claude/plugins/claude-hud/config.json` | claude-hud element order and display flags. `$HOME` here must be expanded to a real absolute path — claude-hud does not expand it |

No secrets are stored. `fetch-usage-snapshot.sh` reads the OAuth token from the macOS Keychain
at call time and never writes it anywhere.

## Wiring

`~/.claude/settings.json`:

```jsonc
"statusLine": { "type": "command", "command": "~/.claude/statusline.sh", "refreshInterval": 5 },
"hooks": {
  "PreToolUse":  [ { "hooks": [ { "type": "command", "command": "~/.claude/hooks/extra-usage-gate.sh", "timeout": 5 } ] } ],
  "PostToolUse": [ { "hooks": [ { "type": "command", "command": "~/.claude/hooks/extra-usage-ack.sh",  "timeout": 5 } ] } ]
}
```

Both hook entries are matcher-less, so they run on every tool call.

## Why a segment you expect is not on screen

Every segment here is conditional. Absence is the normal state for most of them, so before
treating a missing segment as a bug, check the condition:

- **`⚠ EXTRA USAGE` (red, line 1)** — only at **100%** of the 5h or 7d window. Between 90% and
  99% you get an orange `◔ 5h NN% · resets in …` instead. Below 90%, nothing at all.
- **`Extra (Monthly) $N` (claude-hud line)** — `fetch-usage-snapshot.sh` only emits this label
  when the account reports `extra_usage.is_enabled == true` **and** `used_credits > 0`. An
  account whose extra-usage credits are exhausted comes back `is_enabled: false` with
  `disabled_reason: "out_of_credits"`, and the label correctly disappears. To check the live
  values rather than guessing, run `scripts/fetch-usage-snapshot.sh` and read
  `~/.claude/usage-external.json`, or query the endpoint directly.
- **`Agent <name>` (line 1, magenta)** — only when the payload carries `.agent.name`.
- **`general-purpose [sonnet-5]` and friends (claude-hud activity line)** — only while a
  subagent is actually running. It vanishes the moment the agent finishes, so seeing it is a
  function of when you look.
- **Per-model weekly windows (e.g. `Fable 17%`)** — only for models the account has a scoped
  weekly limit on, and only while `usage-external.json` is fresher than
  `externalUsageFreshnessMs` (15 min).

Known limitation: a background agent's status line receives the **host session's** payload, so
line 1's Model segment names the host's model, not the agent's. Per-agent identity on line 1
needs upstream support; claude-hud's activity line is the workaround, since it lists each
running agent with its own model.

## Verifying a change without waiting for a real render

```bash
echo '{"session_id":"t","workspace":{"current_dir":"'"$PWD"'"},"model":{"display_name":"Opus 5"},
"rate_limits":{"five_hour":{"used_percentage":100,"resets_at":'"$(( $(date +%s) + 3600 ))"'},
"seven_day":{"used_percentage":47,"resets_at":'"$(( $(date +%s) + 86400 ))"'}}}' | ./statusline.sh
```

Vary `used_percentage` across 45 / 92 / 100 to exercise the hidden, warning, and alarm branches.
Feeding the same JSON to `hooks/extra-usage-gate.sh` after pointing `usage-state.json` at it
exercises the gate the same way.

One footgun: a manual run writes its fake percentages into `~/.claude/usage-state.json`, which
is the file the gate reads, so a 100% test briefly arms the gate for real. A live session's own
render overwrites it within a few seconds, but in a session that is idle it will sit there —
re-render or restore the file before walking away.
