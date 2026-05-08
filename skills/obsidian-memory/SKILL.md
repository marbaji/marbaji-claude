---
name: obsidian-memory
description: Use at the start and end of every Claude Code session, and whenever you need to recall past work — loads and persists context via an Obsidian vault, saves session logs automatically, searches prior sessions, and maintains an evolving project knowledge graph.
---

# Obsidian Memory Management

This skill provides persistent memory and context management for Claude Code using Obsidian.

---

> **Read `references/gotchas.md` before using this skill.** It lists the failure modes the skill has hit in real runs — non-existent CLI subcommands, vault-path confusion between `obsidian` CLI and the Write tool, and the session-end approval step that must never be skipped.

---

## Step 0 — Setup Detection (Always Run First)

Before doing anything else, check if this skill has been configured:

```bash
cat ~/.claude/obsidian-vault-name 2>/dev/null
```

- **File exists** → read the vault name, use it in place of `<VAULT_NAME>` throughout this skill. Proceed normally.
- **File does not exist** → run the **Installation Flow** below before proceeding.

---

## Installation Flow (First-Time Only)

Read and follow `references/installation-flow.md` in this skill's directory. It contains the full setup wizard (vault creation, folder scaffolding, confirmation).

---

## Vault Location

Read from `~/.claude/obsidian-vault-name`. Use this value as `<VAULT_NAME>` in all commands below.

**Resolving the full filesystem path** (needed for the Write tool):

The Write tool **does not expand `~`**. You must pass a fully-resolved absolute path. Resolve once at session start:

```bash
echo "$HOME/Documents/<VAULT_NAME>"
# e.g. /Users/mohannadarbaji/Documents/Claude Code Obsidian
```

Use that absolute path for every Write call this session. Examples:
- `Context/current-focus.md` in obsidian commands → Write tool path = `/Users/mohannadarbaji/Documents/Claude Code Obsidian/Context/current-focus.md`
- `Work/Chalktalk/Projects/renewal-cards.md` → `/Users/mohannadarbaji/Documents/Claude Code Obsidian/Work/Chalktalk/Projects/renewal-cards.md`

`~/Documents/...` looks fine in conversation prose but the Write tool will fail with a generic "Error writing file" if you actually pass it. The `obsidian` CLI tolerates `~`; the Write tool does not.

Use obsidian CLI commands with `vault="<VAULT_NAME>"` for read/create/append. Use the Write tool with the **resolved absolute filesystem path** for overwrites — and Read the file first in this session (Write blocks unread files).

---

## Vault Structure

```
Context/
  about-me.md              — Who the user is (work, personal, background)
  current-focus.md         — Active/ongoing/complete projects with wikilinks
  preferences.md           — Working style preferences
  work-context.md          — Domain knowledge
  Project Backlog.md       — Manually maintained by user. Read-only for Claude.

Work/Chalktalk/Projects/
  project-name.md          — One file per ChalkTalk work project

Work/Chalktalk/People/     — One note per ChalkTalk team member; backlinks aggregate 1:1s + competency evidence
  <first-last>.md          — See references/people-template.md for schema
  _index.md                — Folder index

Work/Chalktalk/Departments/  — Top-level org units with head + sub-teams + member roster
  Customer Experience.md, Engineering.md, Sales.md
  _index.md

Work/Chalktalk/Competencies/  — Competency notes mirrored from Notion role scorecards
  <Role Folder>/<Competency>.md  — See references/competency-template.md for schema
  _index.md (top-level + per-role)

Work/Chalktalk/1-on-1s/    — Dated 1:1 meeting notes; folder scaffolded but capture flow is future work
  <First Name> YYYY-MM-DD.md  — See references/one-on-one-template.md
  _index.md

Work/Chalktalk/Decisions/  — Decisions of lasting consequence; auto-extracted by session-end ritual
  YYYY-MM-DD-<slug>.md     — See references/decision-template.md
  _index.md

Work/Chalktalk/Reviews/    — Employee review drafts produced by the employee-review skill
  <period>/<First Last>.md
  _index.md

Work/Chalktalk/Values.md   — ChalkTalk's 7 paired company values; link target for value-aligned work
Work/Chalktalk/Shipping Log.md  — Date-ordered log of what ChalkTalk shipped; feeds board/investor updates

Personal/Projects/
  ProjectName/             — Subfolder per personal project (e.g. InBloom Early Learning/)
    overview.md            — Main project doc
    (other docs as needed)

Personal/Brag Doc.md       — Mo's running log of personal wins; separate from company shipping
Personal/Quarterly Reviews/  — Cross-quarter syntheses produced by the quarterly-review skill
  YYYY-Q[1-4].md

Sources/
  YYYY-MM-DD-description.md  — URL source files with summary + takeaways

Sessions/YYYY-MM/
  YYYY-MM-DD-topic.md      — Session logs with wikilinks to projects

Technical/
  Learnings/               — Technical notes and lessons
  Setup/                   — Tool/environment documentation

Templates/
  project.md, session-log.md, etc.
```

---

## File Write Decision Tree

Before writing to any file, follow this decision tree:

| Scenario | Tool to Use | Example |
|---|---|---|
| **New file** (does not exist yet) | `obsidian create` | `obsidian create path="Work/Chalktalk/Projects/new-project.md" content="..." vault="<VAULT_NAME>"` |
| **Overwrite existing file** | **Write tool** (resolved absolute path; Read first) | Write tool targeting `/Users/<username>/Documents/<VAULT_NAME>/Context/current-focus.md` (NOT `~/Documents/...` — see Vault Location for why) |
| **Append to existing file** | `obsidian append` | `obsidian append file="Technical/Learnings/lessons-learned" content="..." vault="<VAULT_NAME>"` |
| **Update frontmatter property** | `obsidian property:set` | `obsidian property:set file="..." property="status" value="complete" vault="<VAULT_NAME>"` |

> **WARNING:** `obsidian update` does not exist. Never use it. If you need to change an existing file's content, read it first, then use the Write tool to overwrite it at the full filesystem path.

---

## Core Functions

### 1. Session Start — Load Context (Proactive)
**When to use**: At the beginning of EVERY new conversation session

**What to do**:

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

**Do NOT ask permission** — just do this automatically at session start.

**Priority order**:
1. current-focus.md (what user is working on)
2. Active project docs (deep context on each)
3. preferences.md (how user likes to work)
4. Project Backlog (read-only, for awareness)
5. Recent sessions (continuity)
6. Other context files as needed (about-me, work-context)

---

### 2. Session End — Update Projects, Then Log (Automatic)
**When to use**: When user says "done", "exit", "that's all", or similar session-ending phrases

**This is the most important function.** The primary outputs of session-end are updated project docs, current-focus, and a session log.

#### Step 1: Identify projects touched

Look at what was worked on during the session. For each distinct project touched, determine:
- **Project name**: Short, descriptive name
- **Category**: `Work/Chalktalk/Projects` (ChalkTalk) or `Personal/Projects/<SubfolderName>`
- **Status**: `active`, `ongoing`, `complete`, `blocked`
- Whether a project doc already exists

**Default category is ChalkTalk** (`Work/Chalktalk/Projects`). Only use `Personal/Projects` for clearly personal work (InBloom, side projects, non-ChalkTalk).

#### Step 2: Present summary for approval

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

#### Step 3: Create or update project docs

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
  path="Work/Chalktalk/Projects/<project-name>.md" \
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

#### Step 4: Update current-focus.md

Read current-focus.md, then rewrite it to reflect reality:
- Add new projects under the correct section (Active / Ongoing / Complete)
- Move completed projects to Complete section with ✅
- Update one-line descriptions if they've changed
- Update priorities list
- Use wikilinks: `[[Work/Chalktalk/Projects/project-name|Display Name]]`

Write the updated file directly (the `obsidian update` command doesn't exist — use the Write tool on the vault path).

#### Step 5: Write session log

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
- [[Work/Chalktalk/Projects/project-name|Project Name]] — what was done
- [[Personal/Projects/InBloom/overview|InBloom]] — what was done

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

**Note:** Source logging (Core Function #9) runs during this step and any other save ritual (mid-session save, "log progress"). Whenever URLs were shared, create source files and include the Sources Captured section in the session log.

#### Step 5.5: Extraction Pass

After the session log is written, walk it for content that should live in its own structured file. Read `references/extraction-rules.md` for full triggers + templates. Four extraction types:

1. **Decisions of lasting consequence** → `Work/Chalktalk/Decisions/YYYY-MM-DD-<slug>.md` (use `decision-template.md` schema)
2. **Shipping events** (🟢, "shipped", "merged", "landed", "deployed") → append to `Work/Chalktalk/Shipping Log.md` under current month
3. **Brag-worthy moments** (codified X, led the call to Y, hard call made well) → append to `Personal/Brag Doc.md` under current quarter
4. **New-person mentions** (someone referenced who has no `Work/Chalktalk/People/<slug>.md` yet) → flag for confirmation, do NOT auto-create

Surface candidates as a SINGLE batched confirmation prompt:

```
At session-end I found these to file:
  • DECISION: "<headline>" → Decisions/YYYY-MM-DD-<slug>.md
  • SHIPPING: "<event>" → append to Shipping Log
  • BRAG: "<moment>" → append to Brag Doc Q<N>
  • NEW PERSON: "<Name>" referenced, no People note exists → create? [y/n]
Approve all? Edit any? Skip any?
```

After user approves, apply each extraction. For decisions/brags/shipping, leave a wikilink stub in the source session log so future reads point to the canonical extracted file.

**Do NOT extract** when:
- A decision is a one-off implementation choice (mid-task pivot, captured by `git log`)
- A shipping event is internal-only churn (commit pushed, no feature/customer impact)
- A brag is generic ("had a productive session")

#### Step 6: Confirm to user

```
✅ Session saved:
  - Updated: Adaptivity Algorithm, InBloom
  - Created: Renewal Storytelling (new project doc)
  - Session log: Sessions/2026-03/2026-03-22-topic.md
  - current-focus.md updated
  - Extracted: 1 decision, 2 shipping events, 1 brag entry
  - Flagged: 1 new person (Latha Pillai) — confirm before creating People note?
```

---

### 3. Search Past Work
**When to use**: User asks "what did we do about X" or "find sessions where we worked on Y"

**Commands**:
```bash
# Search all content
obsidian search query="<search-term>" vault="<VAULT_NAME>"

# Search with context (shows matching lines)
obsidian search:context query="<search-term>" vault="<VAULT_NAME>"

# Search by tags
obsidian tags vault="<VAULT_NAME>"
obsidian tag name="<tag-name>" vault="<VAULT_NAME>"

# Find related sessions
obsidian backlinks file="<note-name>" vault="<VAULT_NAME>"
```

### 4. Create Project Documentation
**When to use**: User starts a new project or wants to document existing work (can also happen mid-session, not just at session end)

**What to do**:
1. Determine category (ChalkTalk → `Work/Chalktalk/Projects/`, Personal → `Personal/Projects/<Name>/`)
2. Create project doc with overview, status, key details, next steps
3. Update current-focus to reference new project

### 5. Daily Note
**When to use**: User wants to see today's activity or add quick notes

**Commands**:
```bash
obsidian daily vault="<VAULT_NAME>"
obsidian daily:append content="- <note-text>" vault="<VAULT_NAME>"
obsidian daily:read vault="<VAULT_NAME>"
```

### 6. Quick Capture
**When to use**: User has an idea, decision, or learning to capture

```bash
# Capture idea
obsidian create \
  name="<idea-title>" \
  path="Personal/Ideas/<idea-name>.md" \
  vault="<VAULT_NAME>"

# Capture learning
obsidian append \
  file="Technical/Learnings/lessons-learned" \
  content="\n## $(date +%Y-%m-%d): <learning>\n<details>\n" \
  vault="<VAULT_NAME>"
```

### 7. Task Management
**When to use**: User wants to track tasks across sessions

**Commands**:
```bash
obsidian tasks vault="<VAULT_NAME>"
obsidian tasks todo vault="<VAULT_NAME>"
obsidian tasks file="Context/current-focus" vault="<VAULT_NAME>"
obsidian task file="<file>" line=<line-number> toggle vault="<VAULT_NAME>"
```

### 8. Context Updates
**When to use**: User's role, focus, or preferences change

Read then update the relevant context file. Note: `obsidian update` does not exist. To overwrite a file, use the Write tool targeting the vault path directly.

### 9. Source Logging — Capture URLs with Context
**When to use**: During any save ritual (session end, "log progress," mid-session save) when URLs were shared in the conversation.

If URLs were shared, read `references/source-logging-rules.md` in this skill's directory and follow it. It defines the source file format, two-layer source system (raw Sources/ → aggregated Knowledge/ pages), and naming conventions.

### 10. Competency Evidence Tagging
**When to use**: When a session demonstrates a person on the team performing in a way that maps to one of their role's competencies (e.g., Ciaran's PR review showed "Driven by Detail"; Sajeda's data-clean-up call showed "Collaborator"; Mo's incident response showed "Default to Action").

**What to do**:

1. Identify (a) the person, (b) the competency note that matches their demonstrated behavior, (c) the value (if any) the behavior aligns with.
2. In the relevant section of the session log (typically `## Learnings` or `## Key Decisions`), insert a wikilink to the competency note: `Demonstrated [[Work/Chalktalk/Competencies/<dept>/<Competency>|<Competency>]] (Ciaran) when <one-line context>.`
3. If the behavior strongly aligns with a value, also link the relevant section of `[[Work/Chalktalk/Values]]`.

This is **lightweight tagging in prose**, not a separate file. The competency note's `## Evidence` section auto-aggregates these mentions via Obsidian's backlinks panel — no manual edits to the competency note are needed.

**When NOT to tag**:
- Routine task completion (shipping a small bug fix is not "demonstrating Driven by Detail")
- Behavior already captured by a Decision or 1:1 note that already links the competency
- Cross-team / non-employee references (don't tag external collaborators against ChalkTalk competencies)

The `employee-review` skill walks these backlinks to score reviews. Quality > quantity — fabricated or inflated tags weaken the signal.

---

## Project Doc Update Rules

These rules keep project docs useful without them becoming stale or bloated:

### Status Values
Use in frontmatter `status` field:
- `active` — Currently being worked on
- `ongoing` — Maintenance/recurring work, no end date
- `complete` — Done, no remaining work
- `blocked` — Waiting on something external

### Sections That Get Replaced (not appended)
- **Next Steps** — Always reflects the latest state. Old next steps are gone.
- **Status** — Reflects current reality.

### Sections That Get Prepended (most recent first)
- **Recent Work** — Add today's entry at the top. Keep last 3 entries. Trim older ones to keep the doc from growing forever.

### Sections That Get Appended
- **Related Sessions** — Add wikilink to today's session at the bottom.

### Sections That Only Change When Materially Different
- **Overview**, **Key Findings**, **Technical Details**, **Project Directory** — Only update if something actually changed (e.g., new key finding, moved directory).

### When to Mark Complete
- User explicitly says "this is done" or "project complete"
- All next steps are resolved with no new ones emerging
- When in doubt, leave as active and ask

---

## Project Backlog

The file `Context/Project Backlog.md` is **manually maintained by the user**. It contains:
- Prioritized list of projects the user wants to work on
- Tool references and tips
- Backlog of content/tooling projects to pull from

**Rules**:
- **Read** it at session start for awareness of priorities
- **Never modify** it — the user updates this themselves
- **Reference** it when suggesting what to work on next
- If a backlog item gets started, create a proper project doc in `Work/Chalktalk/Projects/` — don't modify the backlog
- **Cross-reference** when creating new project docs: check if the project maps to a backlog item. If it does, note the backlog reference in the project doc's Overview section (e.g., "This project addresses backlog item #1: '...'"). This links project docs back to the user's original priorities.

---

## Guidelines

### Always Do (Proactive)
- Load context at session start (don't ask)
- Update project docs at session end (with approval)
- Present project summary with categories before writing
- Write session logs that capture what happened
- Update current-focus when projects change status

### Ask First
- Category assignment (ChalkTalk vs Personal) — present for approval
- Creating new project areas or subfolders
- Marking a project complete
- Changing folder structure
- Deleting or moving files

### File Modification
- `obsidian update` does not exist. To overwrite files, use the Write tool on the full vault path
- `obsidian append` works for adding to the end of a file
- `obsidian create` works for new files
- `obsidian property:set` works for updating frontmatter properties

---

## File Naming Conventions
- Sessions: `YYYY-MM-DD-description.md`
- Work projects: `project-name.md` (in `Work/Chalktalk/Projects/`)
- Personal projects: `overview.md` (in `Personal/Projects/<ProjectName>/`)
- Ideas: `idea-name.md`

## Tags to Use
- `#work/chalktalk` — ChalkTalk work
- `#personal` — Personal projects
- `#technical` — Technical notes
- `#decision` — Important decision made
- `#lesson-learned` — Key learning or insight
- `#blocker` — Something blocking progress
- `#idea` — Ideas and brainstorms

## Troubleshooting

If obsidian command not found:
```bash
source ~/.zshrc
```

If vault not found:
```bash
obsidian vaults  # List all vaults
cat ~/.claude/obsidian-vault-name  # Check configured vault name
```

To reconfigure vault:
```bash
rm ~/.claude/obsidian-vault-name
# Then invoke the skill again — setup flow will run
```

## Integration with Other Skills
- **TodoWrite**: Track multi-step tasks, then summarize in session log
- **inventory-checker**: Document setup changes in Technical/Setup/

---

**Remember**: Project docs are the source of truth for project state. Session logs are records of what happened on a given date. Current-focus is the dashboard. This skill should work INVISIBLY in the background — the user shouldn't have to think about memory management.
