# Session Start — Load Context (Proactive)

**When to use**: At the beginning of EVERY new conversation session.

**Do NOT ask permission** — just do this automatically at session start.

## What to do

1. Read current focus to understand active work
   ```bash
   obsidian read file="Context/current-focus" vault="<VAULT_NAME>"
   ```

2. Read active project docs linked from current-focus
   - For each project listed under "Active Projects" or "Ongoing Maintenance", read the linked project doc
   - This gives deep context on each active project, not just the one-liner in current-focus
   ```bash
   obsidian read file="Work/Chalktalk/Projects/<project-name>" vault="<VAULT_NAME>"
   ```

3. Read preferences for working style
   ```bash
   obsidian read file="Context/preferences" vault="<VAULT_NAME>"
   ```

4. Check Project Backlog for any relevant context
   ```bash
   obsidian read file="Context/Project Backlog" vault="<VAULT_NAME>"
   ```
   This file is **manually maintained by the user**. Read it for context but never modify it.

5. Get recent session history (last 3-5 sessions)
   ```bash
   obsidian files folder="Sessions" vault="<VAULT_NAME>"
   ```

6. Briefly summarize context for user:
   - Active projects and their current state
   - Any pending next steps from project docs
   - Current priorities

7. Run vault health check (every 7 days)
   Check if it's been 7+ days since last lint by looking for the most recent lint report:
   ```bash
   obsidian search query="vault-lint-report" vault="<VAULT_NAME>" | head -1
   ```
   If no report exists or the most recent is 7+ days old: read `references/vault-lint-rules.md` in this skill's directory and execute all checks. The rules file defines 6 checks (abandoned projects, broken wikilinks, status drift, orphan docs, stale next steps, empty sections), which ones auto-fix, and the report formatting rules.

## Priority order

1. current-focus.md (what user is working on)
2. Active project docs (deep context on each)
3. preferences.md (how user likes to work)
4. Project Backlog (read-only, for awareness)
5. Recent sessions (continuity)
6. Other context files as needed (about-me, work-context)
