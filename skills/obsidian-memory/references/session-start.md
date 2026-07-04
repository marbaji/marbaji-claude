# Session Start — Load Context (Proactive)

**When to use**: At the beginning of EVERY new conversation session.

**Do NOT ask permission** — just do this automatically at session start.

## If the SessionStart hook fired

If you see a `## obsidian-memory session-start context` block in the system reminders (the hook ran), steps 1–5 are already covered by the hook output. **Skip to step 6** (summarize) and step 7 (weekly lint) directly.

If you don't see that block, run the full ritual below.

## What to do

1. Read current focus to understand active work
   ```bash
   obsidian read file="Context/current-focus" vault="$VAULT_NAME"
   ```

2. Read active project docs linked from current-focus
   - For each project listed under "Active Projects" or "Ongoing Maintenance", read the linked project doc
   - This gives deep context on each active project, not just the one-liner in current-focus
   ```bash
   obsidian read file="Work/$ORG_NAME/Projects/<project-name>" vault="$VAULT_NAME"
   ```
   `$ORG_NAME` comes from `~/.claude/obsidian-org-name` (defaults to `Chalktalk` for back-compat).

3. Read preferences for working style
   ```bash
   obsidian read file="Context/preferences" vault="$VAULT_NAME"
   ```

4. Check Project Backlog for any relevant context (created empty by the installer; safe to read even on a fresh setup)
   ```bash
   obsidian read file="Context/Project Backlog" vault="$VAULT_NAME"
   ```
   This file is **manually maintained by the user**. Read it for context but never modify it.

5. Get recent session history (last 3-5 sessions)
   ```bash
   obsidian files folder="Sessions" vault="$VAULT_NAME"
   ```

6. Briefly summarize context for user:
   - Active projects and their current state
   - Any pending next steps from project docs
   - Current priorities

7. Run vault health check (every 7 days)
   Check the lint report's file age directly (deterministic — the old `obsidian search` dueness check silently rotted and the lint went unrun for months):
   ```bash
   find "<vault-path>/Context/vault-lint-report.md" -mtime +7 -print 2>/dev/null; ls "<vault-path>/Context/vault-lint-report.md" 2>/dev/null || echo "NO REPORT — lint never ran"
   ```
   If the `find` prints the path (7+ days old) or no report exists: read `references/vault-lint-rules.md` in this skill's directory and execute all checks. The rules file defines 8 checks (staleness-sidecar coverage, broken wikilinks, status drift, orphan docs, stale next steps, empty sections, session-log source integrity, wall-of-text lines), which ones auto-fix, and the report formatting rules. Note: stale-project triage (retire/snooze) is NOT part of the lint — it runs automatically at every session end via the helper's staleness gate.

## Priority order

1. current-focus.md (what user is working on)
2. Active project docs (deep context on each)
3. preferences.md (how user likes to work)
4. Project Backlog (read-only, for awareness)
5. Recent sessions (continuity)
6. Other context files as needed (about-me, work-context)
