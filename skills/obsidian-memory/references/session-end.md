# Session End — Compose Manifest, Run Helper, Confirm (Automatic)

**When to use**: When user says "done", "exit", "that's all", or similar session-ending phrases.

**This is the most important function.** The primary outputs of session-end are an updated set of vault artifacts: project docs, current-focus.md, a session log, and any extracted decisions / Shipping Log entries / Brag Doc entries.

Since 2026-05-09 the ritual is **helper-driven**: the agent emits one YAML manifest of session substance and runs `helpers/session_end.py` to render every artifact. The helper validates the manifest with Pydantic, runs a preflight pass (every target inspected before any write), then writes 8–12 files in subprocess. The full schema is documented in [`references/session-end-helper.md`](session-end-helper.md).

The helper templates the **scaffold** — frontmatter, section headers, wikilink path conventions, bullet formats — never the **substance**. Length on summary, stream bodies, decision context/reasoning, etc. is unbounded; the agent decides how much prose to emit. Don't compress prose to "fit a manifest format."

If the helper isn't available (no Python 3.11+, no Pydantic, etc.) or the work is a `Personal/Projects/<SubfolderName>/...` overview update (the helper only writes flat `Work/<Org>/Projects/<slug>.md`), fall back to the prose-driven flow at the bottom of this file.

---

## Step 1: Identify projects touched

Look at what was worked on during the session. For each distinct project, determine:
- **Project name**: short, descriptive
- **Category**: `Work/$ORG_NAME/Projects` (your configured org) or `Personal/Projects/<SubfolderName>` (subfolder layout, fallback flow only)
- **Status**: `active`, `ongoing`, `complete`, `blocked`
- Whether a project doc already exists

`$ORG_NAME` is read from `~/.claude/obsidian-org-name` (defaults to `Chalktalk`). Resolve once at session start and use throughout this ritual.

**Default category is your configured org** (`Work/$ORG_NAME/Projects`). Only use `Personal/Projects` for clearly personal work.

## Step 2: Present summary for approval

> **MANDATORY STEP — NEVER SKIP.** Writing project docs under the wrong category (a personal project filed under Chalktalk, or vice versa) corrupts the knowledge graph. Always present the summary below and wait for explicit user approval before composing the manifest.

```
📋 Session summary — projects to update:

1. **Adaptivity Algorithm** (ChalkTalk) — Update: added 2PL comparison results
2. **New: Renewal Storytelling** (ChalkTalk) — Create new project doc
3. **InBloom** (Personal) — Update: added vendor quotes  ← personal/subfolder, fallback flow

Does this look right? Any category corrections?
```

Wait for user approval. The user may correct categories, add/remove projects, or split a project that should be two.

## Step 3: Surface extractions for batched approval

Walk the session for content that should live in its own structured file. Read [`references/extraction-rules.md`](extraction-rules.md) for full triggers + templates. Four extraction types:

1. **Decisions of lasting consequence** → `Work/$ORG_NAME/Decisions/YYYY-MM-DD-<slug>.md` (use `decision-template.md` schema)
2. **Shipping events** (🟢, "shipped", "merged", "landed", "deployed") → append to `Work/$ORG_NAME/Shipping Log.md` under current month
3. **Brag-worthy moments** (codified X, led the call to Y, hard call made well) → append to `Personal/Brag Doc.md` under current quarter
4. **New-person mentions** (someone referenced who has no `Work/$ORG_NAME/People/<slug>.md` yet) → flag for confirmation; the helper does NOT auto-create People notes

Surface candidates as a SINGLE batched confirmation prompt:

```
At session-end I found these to file:
  • DECISION: "<headline>" → Decisions/YYYY-MM-DD-<slug>.md
  • SHIPPING: "<event>" → append to Shipping Log
  • BRAG: "<moment>" → append to Brag Doc YYYY Q<N>
  • NEW PERSON: "<First Last>" referenced, no People note exists → flag for manual creation? [y/n]
Approve all? Edit any? Skip any?
```

Wait for user approval. Approved items go into the manifest's `extractions` section in Step 4. Skipped items go nowhere.

**Do NOT extract** when:
- A decision is a one-off implementation choice (mid-task pivot, captured by `git log`)
- A shipping event is internal-only churn (commit pushed, no feature/customer impact)
- A brag is generic ("had a productive session")

## Step 4: Compose the YAML manifest

Write the approved content to `/tmp/session-end-<unix-timestamp>.yaml`. The full schema is in [`references/session-end-helper.md`](session-end-helper.md); the structure summary follows.

**Required top-level fields:**

| Field | Type | Notes |
|---|---|---|
| `date` | ISO date (`2026-05-09`) | The session-end date. |
| `topic` | kebab-case slug | Becomes the session log filename. **Must NOT contain `plan`, `spec`, or `design`** — a lifecycle-prefix hook rejects those. Pick neutral synonyms (e.g. `renewal-rollout` instead of `renewal-plan`). |
| `tags` | list of strings | Frontmatter tags for the session log. |
| `last_updated_slug` | string | Updates `current-focus.md` frontmatter `last-updated:` field. Convention: `YYYY-MM-DD-<topic>`. |
| `summary` | string (1–5 sentences typical, length unbounded) | What we set out to do and what we accomplished. Verbatim. |
| `projects_touched` | list of `{slug, note}` | Bullets under "Projects Touched". `slug` resolves to a wikilink. |
| `streams` | list of `{title, body}` | One per major work stream. `body` is verbatim markdown — any nested `###` / `####` headers preserved. Length unbounded. |
| `key_decisions` | string (verbatim markdown) | Bullet list. |
| `learnings` | string (verbatim markdown) | Bullet list. |
| `files_modified` | object | `chalktalk[]`, `marbaji-claude[]`, `other{}`, `local?` — one entry per commit/PR. |
| `next_steps` | string (verbatim markdown) | Bullet list. |

**Optional top-level fields:**

| Field | Type | Notes |
|---|---|---|
| `sources_captured` | list of `{url, title, why}` | URLs encountered during the session. Empty by default. |
| `extractions` | object | `decisions[]`, `shipping_log[]`, `brag[]`, `new_people[]` — populated from the Step 3 approvals. |
| `project_doc_updates` | list | Append a `## YYYY-MM-DD — <title>` section to an existing `Work/<Org>/Projects/<slug>.md`. Preflight fails if the file is missing. |
| `new_project_docs` | list | Write a brand-new `Work/<Org>/Projects/<slug>.md`. Preflight fails on collision. |
| `focus_updates` | object | `remove[]`, `upsert[]`, `move_to_complete[]` for `current-focus.md`. |

**Critical invariants:**
- `streams[*].body`, `summary`, `key_decisions`, `learnings`, `next_steps`, decision file `context` / `options_considered` / `chosen` / `reasoning` / `consequences`, project doc `body` text — all preserved verbatim. Length unbounded. Don't compress to fit.
- `project_doc_updates[]` and `new_project_docs[]` only handle `Work/<Org>/Projects/<slug>.md` (flat layout). For `Personal/Projects/<SubfolderName>/overview.md` use the fallback flow.
- Inline competency tagging (e.g. `Demonstrated [[Work/Chalktalk/Competencies/.../X|X]] (Name) when …`) goes inside `learnings:` or `key_decisions:` verbatim. No structured competency field in v0.1.

## Step 5: (Recommended) Dry-run first

```bash
python3 ~/.claude/plugins/marketplaces/marbaji-claude/skills/obsidian-memory/helpers/session_end.py \
  --manifest /tmp/session-end-<ts>.yaml \
  --dry-run
```

Dry-run validates the manifest, runs preflight, and prints a one-line preview of every write — without mutating the vault. If preflight fails (missing project doc for an update, collision on a new project doc, missing target file for shipping/brag), the helper lists **every** problem in one pass so you can fix the manifest once and retry.

Skip the dry-run only if you're confident the manifest is clean (e.g. you've run the helper many times this week and the targets haven't changed).

## Step 6: Run the helper

```bash
python3 ~/.claude/plugins/marketplaces/marbaji-claude/skills/obsidian-memory/helpers/session_end.py \
  --manifest /tmp/session-end-<ts>.yaml
```

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | All writes succeeded. |
| 1 | Manifest validation error (Pydantic prints the offending field path). |
| 2 | File-write or preflight error (helper prints which section / file failed). |
| 3 | Vault not found. Write `~/.claude/obsidian-vault-path` or pass `--vault-path`. |

Preflight runs **before any write** and aborts the whole run on failure (atomicity guard, Codex adversarial-review finding #4). This means retries with a fixed manifest don't duplicate non-idempotent appends to Shipping Log / Brag Doc / project docs. Fix the manifest, re-run, done.

If exit 0 but a single section failed mid-run (rare — only happens for issues preflight can't catch, like a Decision file race), use `--only` to re-run just that section without redoing the rest:

```bash
python3 ~/.../session_end.py --manifest /tmp/session-end-<ts>.yaml --only extractions
```

Valid section names: `session_log`, `extractions`, `project_doc_updates`, `new_project_docs`, `focus_updates`.

## Step 7: Confirm to user

```
✅ Session saved (helper):
  - Session log: Sessions/2026-03/2026-03-22-<topic>.md
  - Project docs updated: Adaptivity Algorithm, Renewal Storytelling
  - current-focus.md: bumped + 1 upsert
  - Extracted: 1 decision, 2 shipping events, 1 brag entry
  - Flagged: 1 new person (<First Last>) — confirm before creating People note?
```

If a fallback was needed (Personal subfolder updates, etc.), note it in the confirmation:

```
✅ Session saved (helper + prose fallback):
  - Helper-driven: Work/Chalktalk/* artifacts, current-focus.md, session log, extractions
  - Prose fallback: Personal/Projects/InBloom Early Learning/overview.md (subfolder layout)
```

## Why helper-driven

The prose-driven flow makes 8–12 Read/Edit/Write tool calls back-to-back. Each call's payload echoes into the conversation; every subsequent model inference re-reads the accumulated history. The session-end helper carries substance only (the YAML manifest) and writes in subprocess — no echoes.

Measured numbers from the prose flow vs. the helper-driven design:

| Dimension | Prose-driven | Helper-driven |
|---|---|---|
| Conversation history at session end | ~30k tokens | ~10.5k tokens |
| Raw billed input (cumulative) | ~200k tokens | ~25k tokens |
| Wall-clock | 8–10 minutes | <1 minute |

Same files written either way. Same artifacts. Only the path changes.

Full pattern walkthrough: [[Work/Chalktalk/Knowledge/cli-helpers-walkthrough]] in the vault.

---

## Fallback: prose-driven flow (helper unavailable, or Personal subfolder updates)

Use this section when the helper isn't installed, Python 3.11+ / Pydantic isn't available, or the artifact you need to update is a `Personal/Projects/<SubfolderName>/...` overview that the helper doesn't handle.

### Fallback Step A: Create or update project docs

For each approved project from Step 2:

**If project doc exists** → read it, then update:
- **Status field** in frontmatter if changed
- **Recent Work** section: prepend today's work (keep last 3 entries, trim older ones)
- **Next Steps** section: replace entirely (always reflects latest state)
- **Related Sessions**: append wikilink to today's session
- **Any other section** that has materially changed

**If no project doc exists** → create one:

```bash
obsidian create \
  path="Work/$ORG_NAME/Projects/<project-name>.md" \
  content="<generated-project-doc>" \
  vault="<VAULT_NAME>"
```

New project docs include: frontmatter (type, status, started date, tags), Overview (what and why), Status (emoji + label), key details, Next Steps, Related Sessions.

For personal projects, create inside the appropriate subfolder:

```bash
mkdir -p "<vault-path>/Personal/Projects/<ProjectName>"
# Then create overview.md inside it
```

### Fallback Step B: Update current-focus.md

Read `Context/current-focus.md`, then rewrite to reflect reality:
- Add new projects under the correct section (Active / Ongoing / Complete)
- Move completed projects to Complete section with ✅
- Update one-line descriptions if changed
- Update priorities list
- Use wikilinks: `[[Work/$ORG_NAME/Projects/project-name|Display Name]]`

Write the updated file directly with the Write tool on the absolute vault path (the `obsidian update` command does not exist; `~` does not expand in the Write tool — pass `/Users/...`).

### Fallback Step C: Write session log

```bash
obsidian create \
  path="Sessions/$(date +%Y-%m)/$(date +%Y-%m-%d)-<session-topic>.md" \
  content="<session-log>" \
  vault="<VAULT_NAME>"
```

Session log format:

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
Walkthrough of the work in the order it happened.

## Key Decisions
- Decision 1: reasoning

## Learnings
- Technical insights, gotchas, surprises

## Files Created/Modified
- path/to/file — what changed

## Sources Captured
- [[Sources/YYYY-MM-DD-name|Title]] — why relevant

## Next Steps
- What's left to do
```

### Fallback Step D: Apply approved extractions

For each item from Step 3 the user approved:

- **Decisions** → write `Work/$ORG_NAME/Decisions/YYYY-MM-DD-<slug>.md` using `decision-template.md`. Leave a wikilink stub in the source session log's Key Decisions section.
- **Shipping** → append to `Work/$ORG_NAME/Shipping Log.md` under current `## YYYY-MM` (create heading if missing). Format: `- **YYYY-MM-DD** — <label> — <context>. [[Sessions/YYYY-MM/<session-log-name>]]`.
- **Brag** → append to `Personal/Brag Doc.md` under current `## YYYY Q<N>` (create heading if missing). Format: `- **YYYY-MM-DD** — <body>. [[Sessions/YYYY-MM/<session-log-name>]]`.
- **New people** → print to confirm with the user; do NOT auto-create.

### Fallback Step E: Confirm to user

```
✅ Session saved (prose fallback):
  - Updated: <projects>
  - Created: <new-projects>
  - Session log: Sessions/YYYY-MM/YYYY-MM-DD-<topic>.md
  - current-focus.md updated
  - Extracted: <counts>
  - Flagged: <new-person-counts>
```

---

**Note:** Source logging runs alongside this ritual and any other save (mid-session save, "log progress"). Whenever URLs were shared during the session, create source files and include them in `sources_captured` (helper flow) or in the Sources Captured section of the session log (fallback flow). See [`references/source-logging-rules.md`](source-logging-rules.md).
