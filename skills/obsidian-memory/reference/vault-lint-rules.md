# Vault Lint Rules

Run these checks against the vault. Auto-fix what you can, report the rest.

## Checks and Actions

### 1. Abandoned Projects (auto-fix)
Projects listed as Active or Backlogged in current-focus but no session log touching them in 14+ days.

**Action:** Move them to the "Abandoned" section in current-focus.md with day count appended to the heading (e.g., `— 45 days since last session`). **Preserve the description text** underneath each heading — copy it as-is from wherever the project was (Active, Backlogged, etc.). Never delete descriptions when moving projects.

The Abandoned section sits between Complete and Priorities, with this descriptor at the top:
> This is not a bad thing — it's a sign of good prioritization. You can't solve everything. This list is a point of pride as long as you're moving the most important things toward the finish line. These are projects you explored, learned from, and chose not to continue investing in right now.

### 2. Broken Wikilinks
current-focus references a project doc path that doesn't exist in the vault.

If none found, report one sentence: "All N wikilinks in current-focus.md resolved. No broken links." Don't elaborate.

### 3. Status Drift (auto-fix)
Project doc frontmatter `status` field disagrees with its section in current-focus (e.g., doc says `active` but current-focus lists it under Complete).

**Action:** Update the frontmatter to match current-focus (e.g., set `status: complete` and add `completed: YYYY-MM-DD`).

**Report format:** Show a table with **only the rows that have problems**. Do not list projects where status matches — that's noise.

### 4. Orphan Project Docs
Files in `Work/` or `Personal/` not referenced from current-focus.

If orphans have a fixable action (e.g., sub-project docs that should be noted in current-focus, or supporting docs under a parent that needs a navigability link), show a table with the orphan and the suggested fix. If all orphans are legitimate supporting files that need no action, or no orphans exist, use a one-sentence summary like broken wikilinks (e.g., "No true orphans. 5 Datadog RUM supporting docs belong to the RUM Frustration UX Fixes parent.").

### 5. Stale Next Steps (auto-fix)
A project doc's Next Steps section is identical to what it was 3+ sessions ago, or is missing entirely.

**Skip this check for projects in the Abandoned section** — they're intentionally shelved.

For all other projects: **auto-create** a reasonable Next Steps section based on the project doc's content (recent work, status, key findings). If the project is too ambiguous to derive next steps, **ask the user in the terminal** what the next steps should be. Never leave unacted instructions in the report — either fix it or ask.

### 6. Empty Sections (auto-fix)
Project docs with blank Overview, Key Findings, or Next Steps.

**Skip this check for Abandoned projects.** For active/backlogged/ongoing projects: auto-create the section with reasonable content if possible, or ask the user.

## Output

Save report to `Context/vault-lint-report.md` (overwrite each time). Present a compact summary to the user during session start.

## Auto-fix vs Report

The lint auto-fixes: abandoned projects (moves to Abandoned section preserving descriptions), status drift (updates frontmatter), and stale/empty sections (creates reasonable content or asks user). Broken wikilinks and orphan docs are reported — with actionable commands only when there's a fixable action.

## Report Formatting Rules

- Each section that found zero issues: one-sentence summary, no table, no elaboration
- Each section that auto-fixed issues: state what was auto-fixed with a one-liner per item
- Each section with issues needing user action: show a table or list of items with clear actions
- Never show "OK" rows in tables — only rows with problems
- End the report with a tally: "Auto-fixed N items. M items need manual action."
