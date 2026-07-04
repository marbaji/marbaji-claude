# Vault Lint Rules

Run these checks against the vault. Auto-fix what you can, report the rest.

## Checks and Actions

### 1. Staleness Sidecar Coverage (report-only)
Stale-project handling moved to the session-end staleness sweep (`session_end.py --stale-check` + preflight gate — see `session-end.md` Step 2b), which asks the user retire/complete/snooze/keep per project instead of auto-moving anything. **Do NOT move projects to an "Abandoned" section from the lint.**

The lint's only job here: verify every project under `## Active Projects` and `## Backlog` in current-focus has an entry in `Context/.focus-meta.json`. Missing entries self-heal at the next `--stale-check` run, so just report them in one sentence (e.g., "2 projects missing sidecar entries; will seed on next session-end sweep").

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

**Skip this check for projects in the Retired Projects section and for currently-snoozed projects** (per `Context/.focus-meta.json`) — they're intentionally shelved.

For all other projects: **auto-create** a reasonable Next Steps section based on the project doc's content (recent work, status, key findings). If the project is too ambiguous to derive next steps, **ask the user in the terminal** what the next steps should be. Never leave unacted instructions in the report — either fix it or ask.

### 6. Empty Sections (auto-fix)
Project docs with blank Overview, Key Findings, or Next Steps.

**Skip this check for Retired projects.** For active/backlogged/ongoing projects: auto-create the section with reasonable content if possible, or ask the user.

### 7. Session Log Source Integrity (auto-fix when possible)
Every bullet under `## Sources Captured` in any `Sessions/**/*.md` must be a `[[Sources/<name>|Title]]` wikilink pointing to an existing `Sources/<name>.md` file. This lint is the backstop for the PostToolUse hook (`~/.claude/hooks/check-session-log-sources.py`) — it catches sessions that pre-date the hook, were written from subagents, or slipped through for any other reason.

Scan every session log. For each `## Sources Captured` section, flag:
- **Raw URL bullets** (no wikilink at all) — the source file was never created.
- **Broken wikilinks** — bullet references `[[Sources/foo]]` but `Sources/foo.md` doesn't exist.

**Action:**
- If the URL is publicly fetchable (standard article) and the session log has enough context to summarize it: **auto-create** the `Sources/YYYY-MM-DD-name.md` file using the source-logging template, then replace the raw URL bullet with a proper wikilink.
- If the URL is JS-gated/paywalled (X, LinkedIn, Substack) or session context is insufficient: **report** with a one-line suggestion (e.g., "Run Playwright to capture, then create Sources/...").
- For broken wikilinks: report the expected filename and ask whether to rename an existing nearby file or create a new one.

**Report format:** one row per offending session log with the offending bullets. If all session logs pass, one-sentence summary: "All N session logs have clean Sources Captured sections."

### 8. Wall-of-Text Lines (auto-fix)
Agent-written notes sometimes arrive as single-line paragraph dumps (one 1,000+ character line, segments joined by " · " or long enumerations) — they render as unreadable walls of text in Obsidian. Scan every vault `.md` for lines >500 characters, excluding: table rows, URL/citation lists, code fences, and YAML frontmatter.

**Action (auto-fix):** split offending lines into bullets at structural boundaries (" · " separators, sentence ends, semicolons) using a FORMATTING-ONLY edit — never reword, reorder, add, or delete a word. Verify each fix with `helpers/word_seq_check.py <backup> <edited>` (word-sequence must be identical; restore the backup on any divergence). Genuine flowing prose with no enumerative structure: leave alone and report instead.

**Report format:** one row per fixed file with before→after monster-line counts; one-sentence summary if clean.

## Output

Save report to `Context/vault-lint-report.md` (overwrite each time). Present a compact summary to the user during session start.

## Auto-fix vs Report

The lint auto-fixes: status drift (updates frontmatter), stale/empty sections (creates reasonable content or asks user), and wall-of-text lines (checker-verified formatting-only splits). Broken wikilinks, orphan docs, and staleness-sidecar coverage are reported — with actionable commands only when there's a fixable action. Stale-project triage itself belongs to the session-end sweep, never the lint.

## Report Formatting Rules

- Each section that found zero issues: one-sentence summary, no table, no elaboration
- Each section that auto-fixed issues: state what was auto-fixed with a one-liner per item
- Each section with issues needing user action: show a table or list of items with clear actions
- Never show "OK" rows in tables — only rows with problems
- End the report with a tally: "Auto-fixed N items. M items need manual action."
