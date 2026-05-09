# SessionStart Hook

The skill ships with a SessionStart hook script that injects vault context (current focus, recent sessions, work projects, git activity) at the start of every Claude Code session. This replaces the LLM-driven session-start ritual where the agent reads SKILL.md, current-focus, recent sessions, etc. file-by-file.

**Cost win:** ~3-4x reduction in tokens at session start. Procedural shell, not LLM tokens.

---

## What it injects

The script outputs structured context covering:

1. **Vault info** — vault name, resolved absolute path
2. **Current focus** — full dump of `Context/current-focus.md` (the dashboard)
3. **Project backlog** — first 50 lines of `Context/Project Backlog.md` (read-only, user-maintained)
4. **Recent sessions** — last 5 session log paths (paths only, not content)
5. **Work projects** — file listing of `Work/<YourOrg>/Projects/` (paths only)
6. **Git activity** — branch, recent commits, working tree changes for current cwd if it's a git repo
7. **Reminders** — the retrieval rule and key gotchas

Total output is typically 5-6K tokens. The agent should NOT re-read these files unless it needs the deeper content.

## Wire-up

Add this entry to `~/.claude/settings.json` under `hooks.SessionStart`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/<username>/.claude/skills/obsidian-memory/scripts/session-start-context.sh"
          }
        ]
      }
    ]
  }
}
```

Replace `<username>` with your macOS username. The path matches where the marketplace install syncs the skill locally.

If you keep the skill in a non-standard location, point at that path instead.

## Verification

Run the script manually to verify output looks right:

```bash
~/.claude/skills/obsidian-memory/scripts/session-start-context.sh
```

The script is a no-op if `~/.claude/obsidian-vault-name` is missing (skill not configured) or the vault path doesn't exist (new machine). Safe to wire up before the vault is fully populated — it'll start emitting context once setup completes.

## Edge cases handled

- Vault name file missing → exit 0 silently
- Vault path missing → emit warning to stderr, exit 0 (does not block session)
- `Context/current-focus.md` missing → skip that section
- `Context/Project Backlog.md` missing → skip that section
- Not in a git repo → skip git section
- Vault name with spaces (e.g. "Claude Code Obsidian") → handled correctly

## When NOT to wire it up

- You don't use Claude Code (skill works without the hook; the hook is a token-cost optimization)
- You want the agent to read the files itself for some reason (debugging, audit)
- You're sharing the machine and the vault contains content you don't want injected at session start
