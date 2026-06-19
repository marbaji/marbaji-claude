# Session End — Compose Manifest, Run Helper, Confirm (Automatic)

**When to use** — run the FULL ritual (Steps 1 through 8) when the user says any of:
- "done", "exit", "wrap up", "that's all", "thanks all done"
- "save to obsidian", "save progress", "save this", "save this session", "log this", "log progress", "capture this"
- any "save" / "log" / "capture" verb pointed at obsidian / the vault / the session

**Do NOT shortcut to a single Write tool call** because the scope looks small. Even when there are no project docs to update and no decisions to extract, the ritual still:
1. presents the projects-touched summary for user approval (Step 2 — MANDATORY)
2. surfaces extraction candidates as a single batched confirmation (Step 3 — MANDATORY)
3. emits the manifest (with empty arrays for unused sections — that's fine)
4. runs the helper, which writes the session log + any extractions atomically and prints the change report

A "narrow" session-end (just a session log, no other artifacts) is just a manifest with empty `extractions`, `project_doc_updates`, `new_project_docs`, and `focus_updates` lists. The helper handles that case fine. The cost overhead of composing the manifest is small; the cost of skipping the approval step is high (wrong-category writes corrupt the knowledge graph).

**This is the most important function.** The primary outputs of session-end are an updated set of vault artifacts: project docs, current-focus.md, a session log, and any extracted decisions / Shipping Log entries / Brag Doc entries.

Since 2026-05-09 the ritual is **helper-driven**: the agent emits one YAML manifest of session substance and runs `helpers/session_end.py` to render every artifact. The helper validates the manifest with Pydantic, runs a preflight pass (every target inspected before any write), then writes 8–12 files in subprocess. The full schema is documented in [`references/session-end-helper.md`](session-end-helper.md).

The helper templates the **scaffold** — frontmatter, section headers, wikilink path conventions, bullet formats — never the **substance**. Length on summary, stream bodies, decision context/reasoning, etc. is unbounded; the agent decides how much prose to emit. Don't compress prose to "fit a manifest format."

If the helper isn't available (no Python 3.11+, no Pydantic, etc.), fall back to the prose-driven flow at the bottom of this file.

---

## Step 1: Identify projects touched

Look at what was worked on during the session. For each distinct project, determine:
- **Project name**: short, descriptive
- **Category**: `Work/$ORG_NAME/Projects` (your configured org) or `Personal/Projects/<DisplayName>` (personal subfolder layout)
- **Status**: `active`, `ongoing`, `complete`, `blocked`
- Whether a project doc already exists

`$ORG_NAME` is read from `~/.claude/obsidian-org-name` (defaults to `Chalktalk`). Resolve once at session start and use throughout this ritual.

**Default category is your configured org** (`Work/$ORG_NAME/Projects`). Only use `Personal/Projects` for clearly personal work. Personal projects are now fully supported by the helper — set `category: personal` in the manifest; no fallback required.

## Step 2: Present summary for approval

> **MANDATORY STEP — NEVER SKIP.** Writing project docs under the wrong category (a personal project filed under Chalktalk, or vice versa) corrupts the knowledge graph. Always present the summary below and wait for explicit user approval before composing the manifest.

```
📋 Session summary — projects to update:

1. **Adaptivity Algorithm** (ChalkTalk) — Update: added 2PL comparison results
2. **New: Renewal Storytelling** (ChalkTalk) — Create new project doc
3. **InBloom Early Learning** (Personal) — Update: added vendor quotes  ← category: personal, helper handles this

Does this look right? Any category corrections?
```

Wait for user approval. The user may correct categories, add/remove projects, or split a project that should be two.

## Step 2b: Staleness sweep (retire / complete / snooze) — MANDATORY

Before composing the manifest, surface stale Active projects so the list stays honest (otherwise Active only grows — finished and abandoned work piles up because nothing sweeps it out). Run:

```bash
python3 ~/.claude/plugins/marketplaces/marbaji-claude/skills/obsidian-memory/helpers/session_end.py --stale-check
```

This prints (JSON) every Active project untouched for ≥30 days and not currently snoozed, e.g. `[{"slug": "foo", "last_touched": "2026-05-01", "days_stale": 49}]`. For EACH candidate, ask the user one question — **retire / complete / snooze / keep**:

```
"<slug>" hasn't been touched in <N> days. Retire it, mark complete, snooze 2 weeks, or keep active?
```

Map the answer into the manifest's `focus_updates`:
- **retire** → `move_to_retired: [slug]` (→ `## Retired Projects`, 🗄️ marker)
- **complete** → `move_to_complete: [slug]` (→ `## Complete`, ✅ marker)
- **snooze** → `snooze: [slug]` (14-day reminder; re-snoozing later just resets the window — no cap)
- **keep** → do nothing (it resurfaces in 30 days)

Staleness state lives in the vault-hidden sidecar `Context/.focus-meta.json`, maintained automatically: every `upsert` stamps `last_touched`; `move_to_complete` / `move_to_retired` / `remove` drop the entry. Never hand-edit it.

The sweep catches *abandoned* work AND *shipped-but-forgotten* work (a merged project nobody revisited goes stale and surfaces with a "complete" option). It does NOT watch GitHub, so a silently-merged project can lag up to 30 days before it's flagged — real-time merge detection is a separate follow-up.

## Step 3: Surface extractions for batched approval

Walk the session for content that should live in its own structured file. Read [`references/extraction-rules.md`](extraction-rules.md) for full triggers + templates. Four extraction types:

1. **Decisions of lasting consequence** → `Work/$ORG_NAME/Decisions/YYYY-MM-DD-<slug>.md` (use `decision-template.md` schema)
2. **Shipping events** (🟢, "shipped", "merged", "landed", "deployed") → append to `Work/$ORG_NAME/Shipping Log.md` under current month
3. **Brag-worthy moments** → append to `Personal/Brag Doc.md` under current quarter. Apply the **Cold-Reader Test** (see [`extraction-rules.md`](extraction-rules.md) section (c)) to every candidate: would a stranger reading the single line in 2 years, with zero context, think "this person delivered something exceptional"? No default frequency in either direction — let the test decide.
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

**Cross-link shipping/brag entries to extracted Decisions.** When a shipping or brag bullet references substance captured in a Decision extraction from the same session, populate that entry's `see_also` field with the Decision's wikilink (`[[Work/$ORG_NAME/Decisions/YYYY-MM-DD-<slug>]]`). The bullet renders with ` · See [[<wikilink>]]` segments after the session back-link, giving a Shipping Log / Brag Doc reader a direct path to the canonical record without round-tripping through the session log. Multiple `see_also` entries render in array order. See [`session-end-helper.md`](session-end-helper.md) schema for the field.

**Generalized lessons appendix (when a Decision enumerates many findings).** When the approved batch includes a Decision whose `chosen:` (or equivalent) enumerates 3+ findings, defects, observations, or instances sharing a structural pattern, surface a candidate appendix in the same approval round:

```
Generalized lessons appendix candidate (n patterns identified
under the X instances above):
- <Pattern name>: <one-line description>. Covers <F-cites>.
- <Pattern name>: <one-line description>. Covers <F-cites>.
- ...
Approve appendix? Edit? Skip?
```

If approved, the Decision file gains a `## Generalized lessons` (or `## Generalized antipatterns`) section appended to `chosen:` or `consequences:` consolidating the patterns. If existing [[Knowledge/...]] notes cover any of them, link to them; otherwise propose a new Knowledge note in the same batch:

```
NEW Knowledge note candidate:
  path: Work/$ORG_NAME/Knowledge/<slug>.md
  purpose: <what cross-skill audit it enables>
  patterns: [<list>]
Approve? Edit? Skip?
```

See [`extraction-rules.md`](extraction-rules.md) for the full rule.

**Do NOT extract** when:
- A decision is a one-off implementation choice (mid-task pivot, captured by `git log`)
- A shipping event is internal-only churn (commit pushed, no feature/customer impact)
- A brag fails the Cold-Reader Test in `extraction-rules.md` section (c) (meta-cognition, copy iteration, normal craftwork, anything only intelligible if you were in the room)

## Step 3a: Route learnings to write-time homes (closed learning loop)

Vault session logs are searchable storage, not write-time context. A lesson that lives ONLY in a session log is the system's own "Re-Learned Lesson" failure mode: nothing loads it before the next session repeats the mistake. Before composing the manifest, walk the draft `learnings:` bullets and classify each one's durable home:

| Lesson shape | Durable home | Action at session-end |
|---|---|---|
| Agent behavior / cross-session habit ("when X, always Y") | Claude Code auto-memory (`feedback_*.md` + `MEMORY.md` index line in the project's memory dir) | Write with the Write tool immediately after approval — auto-memory is the only home that loads into every future session |
| Repo standard (applies to a path glob in a work repo) | The repo's rules layer (e.g. `.claude/rules/<area>.md` + its `.coderabbit.yaml` lockstep block) | Queue for the **Step 8 forcing function** below — never park it as a `next_steps` bullet |
| Skill-specific gotcha | That skill's gotchas/reference file | Queue for Step 8 |
| Session-specific detail with no future reader | Vault session log only | Nothing extra — `learnings:` already covers it |

The routing test for the first three rows: **would a future session need this lesson BEFORE it repeats the mistake?** If yes, the session log alone is the wrong home.

Append the routed items to the SAME batched confirmation prompt as Step 3 (for visibility), e.g.:

```
  • LEARNING → auto-memory: "<one-line lesson>" → feedback_<slug>.md
  • LEARNING → repo rule (queued for after the save): "<one-line lesson>" → .claude/rules/<area>.md
  • LEARNING → vault-only: "<one-line lesson>" (no routing)
```

Approved auto-memory items are written directly with the Write tool after the user confirms — they are NOT part of the helper manifest. Repo-rule and gotcha items do NOT go into the manifest at all; they carry forward to Step 8.

## Step 8: Learning forcing function (after the change report)

Immediately after Step 7's change report, surface EACH queued repo-rule / gotcha learning as an inline multiple-choice question (AskUserQuestion-style — the user must pick, not scroll past). One question per learning:

```
Route the learning "<one-line lesson>"?
  1. Open the PR now (Recommended) — write the rule into .claude/rules/<area>.md (with source citation), branch, PR. Rules are single-sourced: CodeRabbit ingests the same file via code_guidelines.filePatterns — no .coderabbit.yaml edit.
  2. Auto-memory instead — personal habit, not a repo standard
  3. Vault-only — session log already captured it
```

On "Open the PR now": do the work in the same session — write the rule with its source citation, update the cited anchor doc in the same PR if the substance is new, open the PR. Docs-only diffs merge immediately per the standing docs-only rule; config-touching diffs follow the standing CR-poll-then-admin-merge workflow. If the session ends mid-poll, the OPEN PR is the durable artifact — visible on GitHub, nagged by CodeRabbit — which is the point: an open PR survives forgetting; a `next_steps` bullet does not.

**CodeRabbit Learnings get a ledger entry in the same breath.** Whenever a `@coderabbitai add a learning: ...` comment is posted (in Step 8 or anywhere in the session), append the learning verbatim to the vault ledger at `Work/Chalktalk/Knowledge/coderabbit-learnings-ledger.md` (date + source PR) before the session ends. The ledger is the portable backup: it survives a CR data wipe and seeds CR setup on personal repos.

Why a forcing function and not a flag: the user's own words (2026-06-11) — "I likely won't remember to do it." A flagged-but-unscheduled item is this step's own Re-Learned Lesson trap applied to itself. The question costs one click; the open loop costs the lesson.

Why this step exists: 2026-06-11, a "HTML must survive no-JS previews" lesson surfaced in an ad-hoc session (no skill run, no PR — so neither the run-trace loop nor the CodeRabbit loop could catch it), and the session log was the only place it landed. Session-end is the one checkpoint ad-hoc sessions reliably hit, so session-end is where lessons get routed to homes that auto-load.

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
| `sources_captured` | list of `Source` objects | URLs encountered during the session. Empty by default. The helper writes one `Sources/YYYY-MM-DD-<slug>.md` per entry before the session log. **Required fields per entry:** `url`, `title`, `slug` (kebab-case), `type` (one of `article`, `github-gist`, `video`, `documentation`, `social-post`, `tool`), `summary`, `why`. Optional: `tags[]`, `takeaways[]`. Session log emits `[[Sources/<date>-<slug>\|<title>]]` wikilinks — do NOT use markdown link form. |
| `extractions` | object | `decisions[]`, `shipping_log[]`, `brag[]`, `new_people[]` — populated from the Step 3 approvals. |
| `project_doc_updates` | list | Update an existing project doc. Supports four structured operations (`status`, `recent_activity`, `next_steps`, `related_session`) and the legacy free-form append (`section_title + section_date + body`, all-or-none). Add `category: personal` to target `Personal/Projects/<slug>/overview.md`. Preflight fails if the file is missing. |
| `new_project_docs` | list | Write a brand-new project doc. Add `category: personal` to write `Personal/Projects/<slug>/overview.md` (parent directory created if absent). Preflight fails on collision. |
| `focus_updates` | object | `remove[]`, `upsert[]`, `move_to_complete[]`, `move_to_retired[]`, and `snooze[]` for `current-focus.md`. `move_to_retired[]` moves entries to `## Retired Projects` (🗄️); `snooze[]` defers a stale project's prompt 14 days via the sidecar (see Step 2b). |

**Structured project-doc update fields (`project_doc_updates[]`):**

| Field | Effect |
|---|---|
| `status` | Replaces body of `## Status` verbatim. Section auto-created if absent. |
| `recent_activity` | `{date, title, body}` — prepends `### YYYY-MM-DD — <title>` under `## Recent activity`; trims to last 3 entries. Section auto-created if absent. |
| `next_steps` | Replaces body of `## Next Steps` verbatim (case-insensitive on Steps/steps). Section auto-created if absent. |
| `related_session` | Appends one `- <value>` bullet to `## Related Sessions`. Section auto-created if absent. Use a wikilink string as the value. |
| `section_title + section_date + body` | Legacy: appends a `## YYYY-MM-DD — <title>` section at end of file. All three must be set together (all-or-none). Can coexist with structured fields. |

At least one of the above must be set per entry (validation error otherwise).

**Personal project notes:**
- Set `category: personal` on `projects_touched[]`, `project_doc_updates[]`, or `new_project_docs[]`.
- The `slug` becomes the Display Name — spaces and Title Case are allowed (e.g. `InBloom Early Learning`).
- Path resolves to `Personal/Projects/<slug>/overview.md`.
- Wikilinks use pipe-alias form: `[[Personal/Projects/<slug>/overview|<slug>]]`.
- No fallback to prose flow needed — the helper handles personal projects natively.

**Critical invariants:**
- `streams[*].body`, `summary`, `key_decisions`, `learnings`, `next_steps`, decision file `context` / `options_considered` / `chosen` / `reasoning` / `consequences`, project doc `body` text — all preserved verbatim. Length unbounded. Don't compress to fit.
- Sources MUST come from `sources_captured[]`. The helper writes `Sources/` files; don't write them separately or use markdown link form in the session log.
- Inline competency tagging (e.g. `Demonstrated [[Work/Chalktalk/Competencies/.../X|X]] (Name) when …`) goes inside `learnings:` or `key_decisions:` verbatim. No structured competency field in v0.1.

## Step 4a — Decide where substance lives

When a session produces both:
- A `streams[*].body` block longer than ~10 lines (full catalog, multi-part defect list, multi-section design write-up), AND
- An `extractions.decisions[*]` capturing the same scope as canonical record,

pick ONE as canonical. The Decision is usually the right home (it's the actionable, indexable artifact a PR author would search for). Let the stream body REFERENCE the decision rather than reproducing it.

Anti-pattern (duplication):

```yaml
streams:
  - title: "Defect catalog"
    body: |
      Tier 1 (one-line): F1 ..., F2 ..., F3 ...
      Tier 2 (small): F4 ..., F5 ...
      [...20 more lines...]
extractions:
  decisions:
    - slug: defect-catalog
      chosen: |
        Tier 1 (one-line): F1 ..., F2 ..., F3 ...
        Tier 2 (small): F4 ..., F5 ...
        [...20 more lines identical to streams body...]
```

Preferred:

```yaml
streams:
  - title: "Defect catalog (run validation surface)"
    body: |
      The validation run surfaced N defects across Y, Z, W.
      Full catalog with file:line cites and prioritized fix tiers
      lives in the extracted Decision:
      [[Work/Chalktalk/Decisions/YYYY-MM-DD-defect-catalog]].
      Highlights:
      - Tier 1 unblocks <X>
      - Tier 2 closes <Y>
      - Tier 3 optional structural lineage work
extractions:
  decisions:
    - slug: defect-catalog
      chosen: |
        [full enumerated catalog with file:line, file paths, fix
        descriptions]
```

The session log stays a chronological narrative; the Decision holds the canonical detail. `project_doc_updates[*].recent_activity.body` can use a SHORTER summary (one bullet per tier with file-only cites, not full descriptions) — that's the right granularity for the project's running history.

This pairs with the `see_also` field on `shipping_log` and `brag` entries: the stream's wikilink-reference to the Decision is the same kind of cross-link a shipping/brag bullet's `see_also` provides.

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

On exit 0, the helper prints a per-file change report showing what each mutator did at the section level (e.g. `## Status: replaced (2 to 4 lines)`, `created (30 lines)`, `skipped (already exists)`). This is visible in the terminal immediately after the run. Pass `--quiet` to suppress the per-file blocks if you only need the trailing `Wrote ...` confirmation line.

## Step 7: Confirm to user

**MANDATORY: quote the helper's per-file change report INLINE in your reply, wrapped in a `diff`-fenced code block.** Claude Code's terminal collapses long Bash tool results by default (`+N lines (ctrl+o to expand)`), so the change report the helper printed is technically visible but practically buried. To surface it AND get red/green coloring on the `- ` and `+ ` lines, paste the helper's stdout into a triple-backtick code block tagged `diff`. Don't summarize the block; quote it verbatim. The user gets the exact section-level view of what changed, in color, without expanding anything.

Format:

````markdown
✅ Session saved (helper):

```diff
<paste the entire helper stdout block here, including the per-file path lines, the operation header lines, the `- ` removed lines, the `+ ` added lines, and the trailing `Wrote session-end artifacts under <vault>.` line>
```

- Flagged: <if any new-person flags from extractions, repeat them here so they're visible alongside the report>
````

The `diff` language tag is what triggers the markdown renderer to color `- ` lines red and `+ ` lines green. Without it the block renders as plain monospaced text.

If you ran with `--quiet`, the helper's stdout will be just the trailing `Wrote ...` line; the in-line block is short and you can summarize separately. Default (with the change report) is the recommended mode.

The block typically runs ~50-80 lines / ~1.5-2k tokens of conversation history per session-end (depends on how much content gets replaced or appended), which is a fixed cost well below the ~30k-token cost of the prose flow's 8-12 echoed Read/Edit/Write tool calls.

If a fallback was needed (helper unavailable), note it in the confirmation. The fallback path doesn't have a structured change report, so a manual summary is fine:

```
✅ Session saved (prose fallback):
  - Prose fallback used: Python/Pydantic not available.
  - Work/Chalktalk/* artifacts, current-focus.md, session log, extractions — written manually.
```

## Why helper-driven

The prose-driven flow makes 8–12 Read/Edit/Write tool calls back-to-back. Each call's payload echoes into the conversation; every subsequent model inference re-reads the accumulated history. The session-end helper carries substance only (the YAML manifest) and writes in subprocess — no echoes.

Measured numbers from the prose flow vs. the helper-driven design:

| Dimension | Prose-driven | Helper-driven |
|---|---|---|
| Conversation history at session end | ~30k tokens | ~10.5k tokens |
| Raw billed input (cumulative) | ~200k tokens | ~25k tokens |
| Wall-clock | 8–10 minutes | <1 minute |

Same files written either way. Same artifacts. Only the path changes. The helper also writes `Sources/` files automatically — no separate agent tool calls needed for source logging.

Full pattern walkthrough: [[Work/Chalktalk/Knowledge/cli-helpers-walkthrough]] in the vault.

---

## Fallback: prose-driven flow (helper unavailable)

Use this section when the helper isn't installed or Python 3.11+ / Pydantic isn't available. Personal projects, structured doc updates, and sources are all handled by the helper — the prose fallback is only needed when Python itself is absent.

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

For personal projects (prose fallback only — the helper handles personal projects natively when Python is available):

```bash
mkdir -p "<vault-path>/Personal/Projects/<ProjectName>"
# Then create overview.md inside it
```

### Fallback Step B: Update current-focus.md

Read `Context/current-focus.md`, then rewrite to reflect reality:
- Add new projects under the correct section (Active / Ongoing / Complete)
- Move completed projects to Complete section with ✅
- Update one-line descriptions if changed
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

**Note:** Source logging runs alongside this ritual and any other save (mid-session save, "log progress"). Whenever URLs were shared during the session, include them in `sources_captured[]` (helper flow) — the helper writes `Sources/YYYY-MM-DD-<slug>.md` files automatically and emits `[[Sources/<date>-<slug>|<title>]]` wikilinks in the session log. In the prose fallback flow, write source files manually and reference them with the same wikilink form. See [`references/source-logging-rules.md`](source-logging-rules.md).
