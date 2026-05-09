# Session End — Update Projects, Then Log (Automatic)

**When to use**: When user says "done", "exit", "that's all", or similar session-ending phrases.

**This is the most important function.** The primary outputs of session-end are updated project docs, current-focus, and a session log.

## Step 1: Identify projects touched

Look at what was worked on during the session. For each distinct project touched, determine:
- **Project name**: Short, descriptive name
- **Category**: `Work/$ORG_NAME/Projects` (your configured org) or `Personal/Projects/<SubfolderName>`
- **Status**: `active`, `ongoing`, `complete`, `blocked`
- Whether a project doc already exists

`$ORG_NAME` is read from `~/.claude/obsidian-org-name` (defaults to `Chalktalk` for back-compat with pre-2026-05 setups). Resolve once at session start and use throughout this ritual.

**Default category is your configured org** (`Work/$ORG_NAME/Projects`). Only use `Personal/Projects` for clearly personal work (side projects, non-work projects).

## Step 2: Present summary for approval

> **MANDATORY STEP — NEVER SKIP.** Writing project docs under the wrong category (e.g. putting a personal project in ChalkTalk, or vice versa) is a high-consequence error that corrupts the knowledge graph. Always present the summary below and wait for explicit user approval before writing anything.

Before writing anything, present a summary to the user:

```
📋 Session summary — projects to update:

1. **Adaptivity Algorithm** (ChalkTalk) — Update: added 2PL comparison results
2. **New: Renewal Storytelling** (ChalkTalk) — Create new project doc
3. **InBloom** (Personal) — Update: added vendor quotes

Does this look right? Any category corrections?
```

Wait for user approval. The user may correct categories or add/remove projects.

## Step 3: Create or update project docs

For each approved project:

**If project doc exists** → read it, then update:
- **Status field** in frontmatter if changed
- **Recent Work** section: prepend today's work (keep last 3 entries, trim older ones)
- **Next Steps** section: replace entirely with current next steps (not append — always reflects latest state)
- **Related Sessions**: append wikilink to today's session
- **Any other section** that has materially changed (e.g., new key findings, new files)

**If no project doc exists** → create one:
```bash
obsidian create \
  path="Work/$ORG_NAME/Projects/<project-name>.md" \
  content="<generated-project-doc>" \
  vault="<VAULT_NAME>"
```

New project docs should include:
- Frontmatter (type, status, started date, tags)
- Overview (what and why)
- Status (emoji + label)
- Key details relevant to the project
- Next Steps
- Related Sessions

For personal projects, create inside the appropriate subfolder:
```bash
mkdir -p "<vault-path>/Personal/Projects/<ProjectName>"
# Then create overview.md inside it
```

## Step 4: Update current-focus.md

Read current-focus.md, then rewrite it to reflect reality:
- Add new projects under the correct section (Active / Ongoing / Complete)
- Move completed projects to Complete section with ✅
- Update one-line descriptions if they've changed
- Update priorities list
- Use wikilinks: `[[Work/$ORG_NAME/Projects/project-name|Display Name]]`

Write the updated file directly (the `obsidian update` command doesn't exist — use the Write tool on the vault path).

## Step 5: Write session log

Create a session log that captures everything that happened:

```bash
obsidian create \
  path="Sessions/$(date +%Y-%m)/$(date +%Y-%m-%d)-<session-topic>.md" \
  content="<session-log>" \
  vault="<VAULT_NAME>"
```

**Session log format:**
```markdown
---
date: YYYY-MM-DD
tags: [session, work/chalktalk]
---

# Session: <Topic>

## Summary
What we set out to do and what we accomplished (2-4 sentences).

## Projects Touched
- [[Work/$ORG_NAME/Projects/project-name|Project Name]] — what was done
- [[Personal/Projects/<SubfolderName>/overview|<Project Name>]] — what was done

## What We Did
Walkthrough of the work in the order it happened. Include:
- Problems encountered and how they were solved
- Commands run and their results (when notable)
- Code changes — what was changed, where, and why
- API calls, data pulled, queries written
- Debugging steps and root causes found

## Key Decisions
- Decision 1: reasoning
- Decision 2: reasoning

## Learnings
- Technical insights, gotchas, or surprises
- Things that didn't work and why
- Useful patterns or approaches discovered

## Files Created/Modified
- path/to/file — what changed

## Sources Captured
- [[Sources/YYYY-MM-DD-name|Title]] — why it was relevant

## Next Steps
- What's left to do
- Open questions or blockers
```

**Note:** Source logging runs during this step and any other save ritual (mid-session save, "log progress"). Whenever URLs were shared, create source files and include the Sources Captured section in the session log. See `references/source-logging-rules.md`.

## Step 5.5: Extraction Pass

After the session log is written, walk it for content that should live in its own structured file. Read `references/extraction-rules.md` for full triggers + templates. Four extraction types:

1. **Decisions of lasting consequence** → `<YourOrg>/Decisions/YYYY-MM-DD-<slug>.md` (use `decision-template.md` schema)
2. **Shipping events** (🟢, "shipped", "merged", "landed", "deployed") → append to `<YourOrg>/Shipping Log.md` under current month
3. **Brag-worthy moments** (codified X, led the call to Y, hard call made well) → append to `Personal/Brag Doc.md` under current quarter
4. **New-person mentions** (someone referenced who has no `<YourOrg>/People/<slug>.md` yet) → flag for confirmation, do NOT auto-create

Surface candidates as a SINGLE batched confirmation prompt:

```
At session-end I found these to file:
  • DECISION: "<headline>" → Decisions/YYYY-MM-DD-<slug>.md
  • SHIPPING: "<event>" → append to Shipping Log
  • BRAG: "<moment>" → append to Brag Doc Q<N>
  • NEW PERSON: "<First Last>" referenced, no People note exists → create? [y/n]
Approve all? Edit any? Skip any?
```

After user approves, apply each extraction. For decisions/brags/shipping, leave a wikilink stub in the source session log so future reads point to the canonical extracted file.

**Do NOT extract** when:
- A decision is a one-off implementation choice (mid-task pivot, captured by `git log`)
- A shipping event is internal-only churn (commit pushed, no feature/customer impact)
- A brag is generic ("had a productive session")

## Step 6: Confirm to user

```
✅ Session saved:
  - Updated: Adaptivity Algorithm, InBloom
  - Created: Renewal Storytelling (new project doc)
  - Session log: Sessions/2026-03/2026-03-22-topic.md
  - current-focus.md updated
  - Extracted: 1 decision, 2 shipping events, 1 brag entry
  - Flagged: 1 new person (<First Last>) — confirm before creating People note?
```
