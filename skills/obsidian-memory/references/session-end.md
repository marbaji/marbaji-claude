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

## Step 2b: Staleness sweep — MANDATORY + code-enforced

Before composing the manifest, surface due projects so the list stays honest (otherwise Active only grows — finished and abandoned work piles up because nothing sweeps it out). Run:

```bash
python3 ~/.claude/plugins/marketplaces/marbaji-claude/skills/obsidian-memory/helpers/session_end.py --stale-check
```

This prints (JSON) every due project with its `section`, e.g. `[{"slug": "foo", "section": "active", "last_worked_on": "2026-05-01", "last_asked_about": null, "days_stale": 49}]`, and self-heals: projects added to current-focus by hand get a sidecar entry seeded with today's date. Two cadences (per-vault overrides in the sidecar):

- **`## Active Projects`** — due when ≥ `stale_days` (default 14) since `last_worked_on` AND any snooze has expired. Question per candidate: **retire / complete / snooze**.
- **`## Backlog`** — monthly grooming: due every `backlog_groom_days` (default 30). Question per candidate: **promote to active / keep in backlog / retire**.

Only ask about the candidates the command prints — never re-ask about projects it didn't flag. There is no separate "keep" answer: keeping a project as-is IS a snooze (the user can name any duration; "snooze" with no duration = 2 weeks for active, and "keep in backlog" = snooze defaulting to the next monthly grooming).

**Every staleness question carries a synopsis of the project — MANDATORY.** A slug is a filename, not a memory aid: by definition these projects have been untouched for weeks, so the user is being asked to retire or complete something they no longer hold in their head. Write two or three sentences saying **what the project is**, then what state it's in. The one-line status blurb in `current-focus.md` is NOT sufficient on its own: it is written as a progress marker for someone already holding the context ("Architecture decided + reorg SHIPPED 2026-08-18. Monthly: sweep.py + claude-mem consolidation."), so it says what happened without ever saying what the thing is. Include it after the synopsis, not instead of it. Where the synopsis makes an option clearly right, recommend that option and say why, in the template's recommendation slot below the question. (Mo, 2026-09-01: *"whenever it tells me about things to snooze or not, it needs to give me a brief overview/synopsis of the project, because otherwise, I forget. I don't know what this project is about"* — said of a bare-slug prompt for a project he had built himself two weeks earlier.)

**Resolve the doc from the wikilink in `current-focus.md`.** `--stale-check` returns no `category` field, so the slug alone does not say whether the doc is `Work/$ORG_NAME/Projects/<slug>.md` or `Personal/Projects/<slug>/overview.md`. The heading above each entry does (`### [[Work/$ORG_NAME/Projects/Content/lesson-production/index]]`, `### [[Personal/Projects/figma-to-site/overview|figma-to-site]]`), and you are already opening the file for the status blurb, so take the path from the same heading. Add `.md` — wikilinks omit the extension.

**If there is genuinely no project doc, say that in the prompt.** Never write a synopsis you could not source — a MANDATORY field is not a license to invent one, and a fabricated project description is worse than a bare slug because the user cannot tell it is fabricated and will retire or complete a project on the strength of it. Say what the entry is, where you looked, and that no doc exists, then ask the question anyway.

```
Active:  "<slug>" — <2-3 sentence synopsis: what it is, what state it's in>.
         Hasn't been worked on in <N> days. Retire, mark complete, or snooze (default 2 weeks — say a different duration if you want)?
         <Recommendation + one line of why, when the synopsis makes one option clearly right.>
Backlog: "<slug>" — <2-3 sentence synopsis: what it is, why it was parked>.
         Has sat in the backlog for <N> days. Promote to current projects, keep in backlog, or retire?
         <Recommendation + one line of why, when the synopsis makes one option clearly right.>
```

Map the answer into the manifest's `focus_updates`:
- **retire** → `move_to_retired: [slug]` (→ `## Retired Projects`, 🗄️ marker)
- **complete** → `move_to_complete: [slug]` (→ `## Complete`, ✅ marker)
- **snooze** / **keep in backlog** → `snooze: [slug]` for the default duration, or `snooze: [{slug: <slug>, days: N}]` for "snooze 3 weeks" etc. Stamps `last_asked_about` but NOT `last_worked_on` (days-stale keeps accruing honestly). Re-snoozing later just resets the window — no cap.
- **promote to active** → `move_to_active: [slug]` — moves the block (description intact) to the top of `## Active Projects` and stamps `last_worked_on` (fresh grace window)

**This step is code-enforced, not honor-system:** the helper's preflight refuses any manifest that leaves a due candidate unaddressed (must appear in one of `move_to_retired[]` / `move_to_complete[]` / `move_to_active[]` / `snooze[]` / `upsert[]` / `remove[]`). If you skipped this step, the apply fails with one problem line per unaddressed slug — ask the user then, and rerun.

Staleness state lives in the vault-hidden sidecar `Context/.focus-meta.json`, maintained automatically: every `upsert` / `move_to_active` stamps `last_worked_on`; every `snooze` stamps `last_asked_about`; `move_to_complete` / `move_to_retired` / `remove` drop the entry. Never hand-edit it.

The sweep catches *abandoned* work AND *shipped-but-forgotten* work (a merged project nobody revisited goes stale and surfaces with a "complete" option). It does NOT watch GitHub, so a silently-merged project can lag up to a full stale window before it's flagged — real-time merge detection is a separate follow-up.

## Step 2c: Close what this session finished — MANDATORY

Every actionable (`spec`, `plan`, `handoff`) sits flat at the top of its container, `~/Desktop/Claude Code/10-projects/<yyyy-mm>-<slug>/` or `20-areas/<slug>/`, and closes by moving into that container's `done/` (rule: the 10-projects bullet in `~/Desktop/Claude Code/CLAUDE.md`). A write-time hook keeps files in the right place, but nothing closes a spec or a handoff except the session that finished it, and Bash writes bypass the hook, so this step is both the closing moment and the backstop.

In order, and the first two rules win over the third:

1. List every actionable this session wrote, edited, or executed (the transcript knows; the fallback is `find "$HOME/Desktop/Claude Code/10-projects" "$HOME/Desktop/Claude Code/20-areas" -maxdepth 2 \( -name 'spec_*.md' -o -name 'plan_*.md' -o -name 'handoff_*.md' \) -newer <a file from session start>`). Zero files means no question and no block.
2. Set aside, and never move, two kinds of file, whatever anyone answers about them: a file whose first body line starts with `**Waiting on Mo:**` (quote that line back; the answer is his, not the session's), and a file another live session owns (a handoff or spec this session did not write and did not execute; name it and leave it).
3. For each remaining file ask ONE multiple-choice question, **finished** or **still open**, with finished recommended whenever this session's own record says the work shipped (a merged PR, a Done section appended, the plan's tasks all checked). Move the finished ones into `<container>/done/`; leave the open ones.

A plan whose PR merged this session is normally already in `done/`: the code-review skill's merge step moves it at merge time. If it is still at the top, it goes through step 3 like anything else.

## Step 3: Surface extractions for batched approval

Walk the session for content that should live in its own structured file. Read [`references/extraction-rules.md`](extraction-rules.md) for full triggers + templates. Six extraction types:

1. **Decisions of lasting consequence** → `Work/$ORG_NAME/Decisions/YYYY-MM-DD-<slug>.md` (use `decision-template.md` schema). Set `category: personal` on the entry for a personal decision and it writes to `Personal/Decisions/` instead — a personal choice does not belong in the work org's decision log, and the slug stays kebab-case either way because it is a filename.
2. **Shipping events** (🟢, "shipped", "merged", "landed", "deployed") → append to `Work/$ORG_NAME/Shipping Log.md` under current month
3. **Brag-worthy moments** → staged to `Personal/Brag Doc.md` `## Staging` (quarter sections are promotion-only). Apply the **Cold-Reader Test** (see [`extraction-rules.md`](extraction-rules.md) section (c)) to every candidate: would a stranger reading the single line in 2 years, with zero context, think "this person delivered something exceptional"? Exceptional is less common than it feels from inside the session — by definition, most sessions produce no brag entry. Let the test decide each time. Before the approval prompt, every candidate must pass the **blind cold-read judge** (same section): one fresh-context subagent that sees only the candidate lines + the rubric, charged to refute and reject by default. Judge rejections are shown in the prompt, not silently dropped.
4. **New-person mentions** (someone referenced in the session) → resolve it yourself: check for `Work/$ORG_NAME/People/<slug>.md`. If it exists, the bucket is **none**. If it's missing, create it after approval (the helper does NOT auto-create — write it with the Write tool from `people-template.md`). **Never ask the user whether a People note exists** — check and act.

   **Do not create a work People note for someone who only appears in personal-category work.** A landlord, a contractor, a family member named in a personal decision is not a work contact, and `Work/$ORG_NAME/People/` has no entry for them precisely because they do not belong there — the missing note is the correct state, not a gap to fill. Flag them to the user instead and let them decide. (There is no `Personal/People/` home today; `stakeholders` on a personal decision should carry a plain name rather than a wikilink into the work org.)

5. **Knowledge** — a durable reference that outlives its project: a taxonomy, a map, a how-to, a walkthrough, anything a future session would look up rather than act on. The test: would a different project want this next quarter? If yes, promote it; the project folder may keep its working copy, the vault copy is canonical. → `<Work/$ORG_NAME|Personal>/Knowledge/<slug>.md`.
6. **Artifacts** — a published Artifact whose HTML source lives with its owner rather than a session scratchpad, so its publish must be logged rather than walked from conversation. Fill this bucket by reading `~/.claude/state/artifacts.jsonl` for rows newer than the last session end, tracked by the stamp file `~/.claude/state/artifacts.last`; surface every unlogged row as a candidate. Approved rows are written to `Context/artifacts.md` and the stamp advances to the newest row's timestamp so the next session-end does not re-surface it.

Surface candidates as a SINGLE batched confirmation prompt:

Every bucket carries a count with **0s shown** — with ONE exception, `STAGED MEMORY`, which is omitted entirely at 0 (see Step 3a.2 for why). Do NOT tag items "(candidate)" — the whole batch is pending the user's approval by definition, so tagging some items is redundant. A bucket with more than one item breaks its items onto indented sub-bullets; a single item or "none" stays inline.

```
At session-end I found these to file:
  • SHIPPING (N): "<event>" → Shipping Log | none
  • BRAG (N): "<moment>" → Brag Doc ## Staging | none
  • (cold-read judge rejected R: "<line>" — <reason>)          ← OMIT when R is 0
  • DECISION (N): "<headline>" → <Work/<Org>|Personal>/Decisions/YYYY-MM-DD-<slug> | none
  • KNOWLEDGE (N): "<title>" → <Work/<Org>|Personal>/Knowledge/<slug> | none
  • NEW PERSON (N): "<First Last>" — creating a People note | none
  • ARTIFACTS (N): "<title>" → Context/artifacts.md | none
  • STAGED MEMORY (N): "<file>" → <home it is going to>      ← OMIT this line entirely when N is 0
Approve all? Edit any? Skip any?
```

**Always print each decision's FULL destination, including the `Work/<Org>` or `Personal` prefix.** That prefix is the only place the work/personal boundary becomes visible to the user, and `category` defaults to `work`, so an omitted category is silent by construction: a personal decision shown as a bare `Decisions/…` gets approved, lands in the work org, and is then swept up by every skill that globs `Work/<Org>/Decisions/*.md` — `board-update`, `investor-update`, `quarterly-review`, `employee-review`. Showing the prefix is what makes Step 2's category approval real for decisions rather than nominal.

Wait for user approval. Approved EXTRACTION items go into the manifest's `extractions` section in Step 4; skipped items go nowhere. **`STAGED MEMORY` is the exception** — it shares this approval block but is not an extraction and has no manifest field. Approving it authorizes the Step 3a.2 sweep, which the agent performs directly with Read/Write/rm; putting it in the manifest would fail schema validation.

**Cross-link shipping/brag entries to extracted Decisions.** When a shipping or brag bullet references substance captured in a Decision extraction from the same session, populate that entry's `see_also` field with the Decision's wikilink, **matching the decision's own category** — `[[Work/$ORG_NAME/Decisions/YYYY-MM-DD-<slug>]]` or `[[Personal/Decisions/YYYY-MM-DD-<slug>]]`. `see_also` is validated for wikilink SHAPE only and is never resolved, so a wrong prefix ships as a dead link. The bullet renders with ` · See [[<wikilink>]]` segments after the session back-link, giving a Shipping Log / Brag Doc reader a direct path to the canonical record without round-tripping through the session log. Multiple `see_also` entries render in array order. See [`session-end-helper.md`](session-end-helper.md) schema for the field.

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
- A decision is a **project-narrative or positioning choice already captured in the project doc**. Reserve a Decision file for a cross-cutting, re-litigable choice someone will search for *out of the session's context* (an architecture call, a policy, a strategic bet). If the project doc already holds it next to the work it governs, a second Decision copy nobody greps for is over-extraction — fold it into the project doc instead.
- A shipping event is internal-only churn (commit pushed, no feature/customer impact)
- A brag fails the Cold-Reader Test or the blind cold-read judge in `extraction-rules.md` section (c) (meta-cognition, copy iteration, normal craftwork, anything only intelligible if you were in the room)

## Step 3a: Route learnings to write-time homes (closed learning loop)

Vault session logs are searchable storage, not write-time context. A lesson that lives ONLY in a session log is the system's own "Re-Learned Lesson" failure mode: nothing loads it before the next session repeats the mistake. Before composing the manifest, walk the draft `learnings:` bullets and classify each one's durable home:

| Lesson shape | Durable home | Action at session-end |
|---|---|---|
| Agent behavior / cross-session habit ("when X, always Y") | **`~/.claude/work-principles.md`** — NOT the project memory dir, which is frozen (see Step 3a.1). The harness may still stage a `feedback_*.md` at correction time; Step 3a.2 sweeps it. | **No session-end enumeration.** Auto-memory writes happen natively at correction time, at Claude's discretion — do not trawl the learnings list for auto-memory candidates at session-end. Only write one here if a clearly durable habit lesson was somehow missed mid-session (rare). Dropped from the counted block 2026-07-31 (Mo, memory-bloat audit: MEMORY.md at 111 entries / ~4k tokens loaded per session, +47 memory files in July alone — the counted bucket double-forced writes on top of the harness's native correction-time behavior). |
| Repo standard (applies to a path glob in a work repo) | The repo's rules layer (e.g. `.claude/rules/<area>.md` + its `.coderabbit.yaml` lockstep block) | Queue for the **Step 8 forcing function** below — never park it as a `next_steps` bullet |
| Skill-specific gotcha | That skill's gotchas/reference file | Queue for Step 8 |
| Session-specific detail with no future reader | Vault session log only | Nothing extra — `learnings:` already covers it |

The routing test for the repo-standard and skill-gotcha rows: **would a future session need this lesson BEFORE it repeats the mistake?** If yes, the session log alone is the wrong home. (The same test governs the discretionary correction-time auto-memory write — it just isn't enumerated or counted here.)

### Step 3a.1: What may enter memory at all, and where (settled with Mo 2026-08-05)

The 2026-07-31 amendment above pulled the FREQUENCY lever (stop enumerating auto-memory candidates
at session-end). It did not fix placement, so the index kept growing anyway: by 2026-08-05 a
**148-file, 7-silo** audit found the chalktalk silo at 97 files / 124 index lines / ~3.4k tokens
loaded per session, a second silo at 43 files, and the two duplicating each other by concept with
zero filename overlap (`user_role` vs `user_profile`, `feedback_no-em-dashes` vs
`feedback_no_em_dashes`, one 95-line "where plans live" file vs four separate ones). Several
memories restated rules already in the global `CLAUDE.md`, paying index tokens to duplicate a file
that already loads everywhere.

Three rules now govern every memory write, including the discretionary correction-time one:

**1. Admission test — which home, and project memory is NOT one of them.** A lesson goes to the home
that loads when it will be needed. **Project `memory/` is frozen (2026-08-05)** — do not write there.
Its scope key was the working directory, not the project, so a lesson learned in one directory was
invisible in every other; that mismatch produced parallel copies of the same rules under different
names across seven silos.

| lesson shape | home | loads |
|---|---|---|
| Cross-project working principle or procedure | **`~/.claude/work-principles.md`** (imported by `~/.claude/CLAUDE.md`) | every session, every project |
| Repo standard scoped to a path glob | that repo's `.claude/rules/<area>.md` | when editing matching paths — and it is versioned and PR-reviewed, so it cannot rot silently |
| Skill-specific trap | that skill's gotchas / references file | when the skill runs |
| Write-up, architecture note, tool recipe, project fact | Obsidian vault (`Knowledge/`, or the project doc) | on search |
| Personal, non-shareable fact about one repo | that repo's `CLAUDE.local.md` (gitignored) | in that repo |
| Already stated in `CLAUDE.md` / `work-principles.md` | nowhere — drop it | a second copy is drift waiting to happen |
| Session-specific detail with no future reader | the vault session log | on search |

The ordering test: **when will this need to fire?** Unprompted before I act → `work-principles.md`.
While editing certain paths → repo rules. While running one skill → that skill. Looked up
deliberately → the vault.

Discriminator on the principle/vault line, applied literally: *"use `git rm -rf --cached` for
path-based tree replacement"* is a procedure I need AT the moment of acting, so it belongs in
`work-principles.md`'s Procedures section. *"Which SQL backs which Canvas model"* is a lookup →
vault.

**2. Fold before you add.** `work-principles.md` has fixed sections, so the question is never
"should I add a principle?" but **"which existing bullet does this sharpen?"** Search it first and
edit in place; add a bullet only when nothing there covers the lesson, and a new SECTION only when
the lesson belongs to no existing group. Editing costs nothing; every addition is loaded in every
session of every project, forever. This is the whole reason a curated file replaced a directory: a
directory accretes by construction, a file can only be edited. (2026-08-05: two learnings both
folded into existing entries — the index did not grow.)

**3. Rule first, incident second.** State the rule, then the incident as a short parenthetical
citation. A memory that opens with the incident and buries the rule in paragraph three reads as *"do
exactly what happened last time"* — which is what makes memories railroady, and railroady memories
get ignored or, worse, over-applied to situations that only rhyme.

### Step 3a.2: Sweep the staging area (MANDATORY)

The harness writes memory files at correction time, at its own discretion — that is correct
behavior (a correction should be captured the moment it happens) and the ritual cannot and should
not suppress it. What the ritual CAN do is stop those captures accumulating. Diagnosis behind this
step: after the 2026-07-31 amendment removed auto-memory from the counted block, **11 new files
still appeared in 5 days**, every one a mid-session correction — so the leak was never session-end
enumeration, it was that each capture minted a permanent file plus an index line.

So treat the memory directory as a **staging area**, not a store. At every session-end:

```bash
MEM="$HOME/.claude/projects/$(pwd | sed 's|[/.]|-|g')/memory"
find "$MEM" -maxdepth 1 -name '*.md' ! -name 'MEMORY.md' 2>/dev/null || true
```

Two details, both verified by running them rather than reasoning about them. **`find` rather than
`ls "$MEM"/*.md`**, because zsh prints `no matches found` when a glob misses even with stderr
redirected — the glob fails before `ls` runs. And **`|| true`** for the case where the memory
directory does not exist at all (a project that never had one): `find` exits `1` there, which can
abort an agent shell running `set -e` / `pipefail`. Note it exits `0` on the ordinary
zero-matches-but-directory-exists case, so the guard is for the missing directory specifically. The
Step 7 snippet needs it for a second reason as well: `grep -c .` exits `1` on empty input. Do NOT
date-filter. Under the freeze the
directory is supposed to be empty, so **every file listed is staged** — which is stricter than mtime
and does not care when a file arrived. (An earlier draft used `find ... -newermt '-1 day'`, which is
GNU-only: stock macOS ships BSD `find` with no `-newermt`, and Claude Code's own `find` shim routes to
`bfs`, which rejects the relative timestamp outright. It would have failed silently in both.)

**The sweep is destructive, so it is approval-gated and verified — never fire-and-forget.**

1. **Surface it in the Step 3 batched approval** as its own bucket, following that block's
   formatting contract exactly — `• STAGED MEMORY (N): "<file>" → <home it is going to>`, multiple
   items broken onto indented sub-bullets. Call it **STAGED MEMORY**, not "sweep": the
   correction-taxonomy step already owns a differently-formatted `LEDGER SWEEP` block, and two things
   called sweep in one ritual is how a format contract gets misapplied.

   **Omit the bucket entirely when nothing was staged** — the one documented exception to the block's
   0s-shown rule (Mo, 2026-08-05). The other buckets show a 0 because it is informative: `SHIPPING (0)`
   could have been 2. This bucket is expected to read 0 *forever*, since the directory staying empty is
   the whole design, so printing it every close is noise that trains the reader to skip the block it
   sits in. **And never narrate the freeze itself.** The routing table is reference material, not
   output: a session that routed a habit lesson to `work-principles.md` should say that and stop, not
   explain why project memory was not eligible.
   Nothing is deleted before the user approves that batch, which keeps the ritual's standing promise
   that the user sees a summary before any write.
2. **Re-home the content first**, per the Step 3a.1 table.
3. **Verify it landed**: confirm a distinctive phrase from the file is present in the destination.
   This is the same protocol the 2026-08-05 consolidation used by hand for all 148 files — a
   fingerprint check in the destination before every removal, which is why nothing was lost.
4. **Only then delete the file, AND remove its `MEMORY.md` pointer line** in the same step. Deleting
   the file alone leaves a dangling pointer and a permanently nonzero pointer count that reports
   unfinished work forever.
5. **If verification fails, leave the file in place and say so.** An unverified re-home is a deletion
   with extra steps.

Report in the Step 7 block: how many were staged, where each went, and any left in place.
A memory directory that is not empty at session-end is unfinished work, not a store — unless a file
was deliberately left by step 5 or the loop guard below, in which case say which.

**Loop guard.** If the harness re-creates a memory it believes is missing, sweeping it again every
session is a loop. So: **the same slug swept twice across sessions gets left alone the third time.**
Leave the file, stop sweeping it, and tell the user the harness appears to be re-asserting it — that
is information about the harness, not a chore to repeat. Record the strike in the session log so the
next session can count it.

Present the routing as a counted **LEARNING ROUTING** block appended to the Step 3 batch. Formatting contract (settled with Mo 2026-07-07):

- The block heading carries the total (sum of the escalation buckets); each bucket heading carries its own count, **0s shown** (never drop an empty bucket).
- Each bucket = a **bold label** + a one-line description of what that home is and when a lesson goes there, then the value(s) on **indented nested `- →` sub-bullets** — always indented, even for a single item or "none" (the arrow alone won't indent; the `-` is what nests it, and the descriptions are long so the value never sits inline).
- **Omit the VAULT-ONLY and AUTO-MEMORY routes** from the presented block: vault-only is the null route (no escalation), and auto-memory is handled natively at correction time (see the table above — 2026-07-31). Show only the escalation homes that session-end alone can catch (repo-rule, skill-gotcha).
- Fold `.claude/rules` and "session log" into the description sentences instead of a `/`-style label.
- (This indented-even-when-single rule is specific to LEARNING ROUTING. Every other section — extractions, ledger sweep — only indents a bucket's items when there is more than one.)

```
🧠 LEARNING ROUTING (N): where each lesson's durable home is —
- **REPO-RULE (n):** a committed rule file in `.claude/rules` that both Claude and CodeRabbit read on every PR, for stable standards scoped to a path glob.
  - → none
- **SKILL-GOTCHA (n):** a specific skill's own gotchas or reference file, for a convention unique to that one skill.
  - → "<one-line lesson>"
```

Repo-rule and gotcha items do NOT go into the manifest at all; they carry forward to Step 8. (Since the 2026-08-05 freeze there is no session-end auto-memory write at all: a missed habit lesson goes to `~/.claude/work-principles.md`, not to the project memory dir. Anything the harness staged there mid-session is swept by Step 3a.2.)

## Step 3b: Correction-taxonomy sweep (evidence-ledger reconcile)

This step is an **opt-in** correction-taxonomy loop. Ledger: `$VAULT_PATH/Personal/Projects/agentic-loops/taxonomy-evidence-ledger.md`. It activates only if that file exists in your vault — create one to opt in (see `adopting-this-skill.md` § "Optional: correction-taxonomy evidence ledger"); otherwise skip this step entirely.

**SKIP this step entirely when the session's work is personal-category** — meaning it touched **at least one** project and every one carries `category: personal`. The "at least one" is load-bearing: "every project touched is personal" is vacuously TRUE for a session that touched no projects at all, which would silently exempt most ad-hoc engineering sessions from the sweep. A session with an empty `projects_touched` does not qualify automatically; judge it on whether its corrections were about the engineering loops. No sweep, no increments, no singletons, and no `LEDGER SWEEP` block in the confirmation. The ledger exists to harden agent behavior on the engineering loops; a personal-life session that happens to involve a landlord, a lease, or a contractor is not that corpus, and sweeping it inflates the tally with hits that no checker will ever bind. A mixed session sweeps only the work-category corrections. (Mo, 2026-08-18: "no ledger sweeps pls on personal work" — said after an InBloom preschool-permitting session produced an increment and a new singleton, both reverted.)

Scan the ending session for moments the user corrected or redirected the agent (the same moments the capture rule logged to `tasks/lessons.md` with a category tag). For EACH correction, run the ledger's four category-maintenance tests in order — (1) definition test: fits an existing category without adding an "and/except" clause? (2) checker test: would that category's existing check have caught it? (3) axis test: does it constrain a different axis? (4) two-instance rule: singletons stay drafts — then:

1. **Existing category fits** → increment that category's hit count and append a citation: session-id + date + a ≤1-line paraphrase. Distillation only — NEVER copy transcript content into the ledger.
2. **No clean fit** → park it as a new singleton under `## Unverified drafts` (same citation format).
3. **A draft just hit its 2nd independent occurrence** → ask the user ONE multiple-choice confirm (recommended option first) to promote it. On promotion: route the RULE to its home per the Step 3a.1 table (skill gotchas | WORKFLOW-GOTCHAS.md | `work-principles.md` | .claude/rules | CR Learning — NOT project memory, which is frozen — reuse the Step 3a / Step 8 machinery for that write) and record in the ledger WHICH of the four tests decided the placement. The rule's home carries the STATEMENT plus at most a one-clause anchor; the ledger keeps the full cited EVIDENCE — that one-hop chain is the settled progressive-disclosure design (Mo, 2026-08-18/19), and the ledger header's admissibility bar governs what counts as evidence.
4. **This session MINTED or PROMOTED a category** → auto-archive the transcript as a durable receipt:

   ```bash
   PROJ_DIR=~/.claude/projects/$(pwd | sed 's|[/.]|-|g')
   SESSION_JSONL=$(ls -t "$PROJ_DIR"/*.jsonl | head -1)   # current session = newest
   cp "$SESSION_JSONL" "$VAULT_PATH/Personal/Projects/agentic-loops/transcripts/<date>-<slug>__<first-8-of-session-id>.jsonl"
   ```

   No privacy gate — the ledger and its transcript archive live only in your private vault, never in a shared repo. Do NOT archive otherwise — routine citations stay session-id + date only, accepting that IDs decay with the retention window while the tally survives.

Ledger writes are direct Edit-tool edits (Read the ledger first this session); they are NOT part of the helper manifest. Zero corrections in the session = zero ledger writes — never invent entries.

**Report format (mandatory, user-set 2026-07-05):** present the sweep's outcome to the user as ONE `LEDGER SWEEP` block with exactly three ALL-CAPS subsections. Every heading carries its count in parentheses — the block heading carries the total (sum of the three) — and each subsection is spelled out even when its count is 0 ("none"). Never collapse the block into a single prose line:

```
LEDGER SWEEP (2)
- INCREMENTS TO EXISTING CATEGORIES (2): <category +1 (id8: ≤1-line paraphrase); ...> | none
- NEW SINGLETONS PARKED (0): <name — one-line definition (id8)> | none
- PROMOTION CANDIDATES - DRAFTS REACHING 2+ SESSIONS (0): <name (sessions)> | none
```

(The third heading uses a hyphen for its qualifier, not nested parentheses — exactly one parenthetical per heading: the count.)

**The block reports the session's FULL ledger delta, not just close-time writes.** An increment or singleton applied live mid-session (the correction was ledgered the moment it happened) is still listed and still counted — mark it `(applied live)` after its paraphrase. Omitting live-applied entries under-reports the session and under-counts the headings.

## Step 8: Learning forcing function (after the change report)

Immediately after Step 7's change report, surface EACH queued repo-rule / gotcha learning as an inline multiple-choice question (AskUserQuestion-style — the user must pick, not scroll past). One question per learning:

```
Route the learning "<one-line lesson>"?
  1. Open the PR now (Recommended) — write the rule into .claude/rules/<area>.md (with source citation), branch, PR. Rules are single-sourced: CodeRabbit ingests the same file via code_guidelines.filePatterns — no .coderabbit.yaml edit.
  2. `~/.claude/work-principles.md` instead — a cross-project habit rather than a repo standard (never the project memory dir, which is frozen)
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
| `focus_updates` | object | `remove[]`, `upsert[]`, `move_to_complete[]`, `move_to_retired[]`, `move_to_active[]`, and `snooze[]` for `current-focus.md`. `move_to_retired[]` moves entries to `## Retired Projects` (🗄️); `move_to_active[]` promotes a Backlog entry to `## Active Projects`; `snooze[]` defers a due project's prompt (default per section, custom via `{slug, days}`) and satisfies the preflight staleness gate — see Step 2b. |

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

## Step 6b: Monthly brag promotion dispatch

After the helper run, check whether the brag promotion pass is due: read the `## Staging` section
of `Personal/Brag Doc.md`; if any entry's date (`- **YYYY-MM-DD**` prefix) is in a month earlier
than the current month, dispatch the promotion subagent IN THE BACKGROUND and note "brag
promotion pass dispatched" in the Step 7 confirmation. Full contract — charter, archive sidecar,
no-approval-gate rationale, inline report wording — lives in
[`extraction-rules.md`](extraction-rules.md) section (c), "Monthly promotion pass". Do not
perform the ranking in the main session: it runs at context exhaustion and the judgment belongs
to a fresh context. When the background agent's completion notification arrives, relay its counts
inline ("promoted N of M, archived K — open the background agent's session for detail").

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

**Also report the memory-index budget** (added 2026-08-05). The cost of a new memory file is invisible at the moment you decide to write one, which is how an index reaches 124 lines. Surface it in the same reply as the change report, one line:

```bash
MEM="$HOME/.claude/projects/$(pwd | sed 's|[/.]|-|g')/memory"
staged=$(find "$MEM" -maxdepth 1 -name '*.md' ! -name 'MEMORY.md' 2>/dev/null | grep -c . || true)
# awk, not `grep -c ... || echo 0`: grep exits 1 on zero matches, so the fallback
# fires ON TOP of grep's own "0" and the variable becomes "0\n0".
pointers=$(awk '/^- \[/{n++} END{print n+0}' "$MEM/MEMORY.md" 2>/dev/null || echo 0)
echo "  memory: $staged staged file(s), $pointers index pointer(s)"
```

Count **files and index pointers, not raw lines** — since the freeze, `MEMORY.md` is a boilerplate stub explaining where things went, so a line count reports ~25 for an empty directory and reads as 25 memories. Both numbers should be **0**, and **when both are 0, report nothing at all** — a line that says "0 staged, 0 pointers" every single close is noise for the same reason the STAGED MEMORY bucket is omitted at 0. Surface it only when a number is non-zero, which means it is the sweep's work. If pointers have grown since the last close, say by how much and why, and check Step 3a.1 — a pointer that should have been a `work-principles.md` edit is the usual cause. Past ~120, `/dream` (merges duplicates, deletes contradicted facts, prunes the index) before adding anything.

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

- **Decisions** → write `Work/$ORG_NAME/Decisions/YYYY-MM-DD-<slug>.md`, or `Personal/Decisions/YYYY-MM-DD-<slug>.md` for a personal decision, using `decision-template.md`. Leave a wikilink stub in the source session log's Key Decisions section, using the SAME path you just wrote to.
- **Shipping** → append to `Work/$ORG_NAME/Shipping Log.md` under current `## YYYY-MM` (create heading if missing). Format: `- **YYYY-MM-DD** — <label> — <context>. [[Sessions/YYYY-MM/<session-log-name>]]`.
- **Brag** → append to `Personal/Brag Doc.md` under `## Staging` (created at end of file if missing; quarters are promotion-only). Format: `- **YYYY-MM-DD** — <body>. [[Sessions/YYYY-MM/<session-log-name>]]`.
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
