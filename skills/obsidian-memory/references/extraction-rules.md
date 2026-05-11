# Extraction Rules

Defines what the session-end ritual extracts from a fresh session log and where each extracted artifact lands. Runs as **Step 4.5** of the session-end ritual — after the session log is written, before the user-facing summary.

Four extraction types: **decisions**, **shipping-log appends**, **brag-worthy moments**, **new-person flags**. Each has explicit triggers, an inclusion regex/substring set, an exclusion list, a destination path with date templating, and a target schema/template.

The extractor must:
1. Scan the just-written session log for trigger matches.
2. Build a single batched confirmation summary (one prompt, all extractions listed).
3. Wait for user confirmation.
4. Apply approved extractions, leave wikilink stubs in the source session log, never duplicate content.

---

## (a) Decision Extraction

Promotes a session-log decision to a standalone Decision note (see `decision-template.md`).

### Triggers

A decision in the session log's `## Key Decisions` section qualifies if **any one** of these matches:

- **Multi-week relevance phrasing** — decision text mentions a horizon of "2 weeks", "this quarter", "going forward", "ongoing", "from now on".
- **Policy / rule shape** — text contains "rule:", "policy:", "always", "never", "we should never", "going to require".
- **Multiple-people scope** — text references 2+ wikilinks to People notes.
- **Supersession language** — text contains "instead of", "replacing", "supersedes", "replaces our prior", "rolling back".
- **Binding-choice phrasing** — text starts with `Decided to`, `Going with`, `Chose X over Y`, `Picked X for Z reason`, `Settled on`.

### Do NOT extract if

- Decision is scoped to a single task ("decided to use Sonnet for this query", "going with regex over LLM for this one extraction").
- Decision is a personal preference with no team impact.
- Decision is already a Decision note (session log references `[[Work/Chalktalk/Decisions/...]]` — that's a back-reference, not a fresh decision).
- Decision is ambiguous or hedged ("might decide to...", "leaning toward...").

### Destination

`Work/Chalktalk/Decisions/YYYY-MM-DD-<slug>.md` — date from the session log, slug derived from the decision title (kebab-case, ~5 words, noun phrase).

### Schema

Use `decision-template.md`. Populate from the session log:
- `owner` — the person primarily accountable (default: Mo if unstated).
- `stakeholders` — every People-note wikilink in the decision text.
- `Source Session` — wikilink to the session log.
- `Context` / `Reasoning` — pulled from surrounding session-log prose.
- `Options Considered` — only if the session log discussed alternatives; otherwise leave a placeholder note ("Options not enumerated in source session — backfill if revisited").

### Stub left in session log

Replace the original `## Key Decisions` bullet with a wikilink:

```markdown
- [[Work/Chalktalk/Decisions/2026-05-08-no-yaml-status-fields-in-model-registry|No YAML status fields in model registry]]
```

### Generalized lessons appendix (when applicable)

When a Decision enumerates 3+ findings, observations, defects, or instances that share a structural pattern, the agent should ALSO surface the generalized pattern(s) underneath them. This makes future "what did we learn" queries answerable from the abstraction layer, not just instance evidence.

At Step 3 (surface extractions for batched approval), when the extracted Decision contains an enumerated catalog, the agent adds a brief candidate list:

```
Generalized lessons appendix candidate (n patterns identified
under the X instances above):
- <Pattern name>: <one-line description>. Covers <F-cites>.
- <Pattern name>: <one-line description>. Covers <F-cites>.
- ...
Approve appendix? Edit? Skip?
```

If approved, the Decision file gains a `## Generalized lessons` section that consolidates the patterns. (Implementation-wise: the appendix is appended inside an existing markdown-bearing field — typically the close of `chosen:` as a `## Generalized antipatterns` section, or `consequences:` if the appendix reflects what to do differently going forward. No schema change required.)

If a `[[Knowledge/...]]` note already covers any of them, the agent links to it; if not, the agent proposes creating a new Knowledge note as a separate extraction candidate in the same Step 3 batch:

```
NEW Knowledge note candidate:
  path: Work/Chalktalk/Knowledge/<slug>.md
  purpose: <what cross-skill audit it enables>
  patterns: [<list>]
Approve? Edit? Skip?
```

Goal: instance-level catalogs (F-numbered defects, ticket lists, SQL fix lists) consistently get their generalized counterpart captured at the same session-end, with no separate user prompt needed.

Reference example: `Work/Chalktalk/Decisions/2026-05-11-non-interpolated-trace-defects.md` (its "Generalized antipatterns surfaced by this catalog" section) and `Work/Chalktalk/Knowledge/skill-runtime-antipatterns.md` together illustrate the artifact pair this rule produces.

---

## (b) Shipping Log Append

Appends an entry to `Work/Chalktalk/Shipping Log.md` under the current month section.

### Triggers

Session log contains **either**:

- The emoji `🟢` (the canonical "shipped" marker), **or**
- One of the verbs `shipped`, `merged`, `landed`, `deployed`, `live`, `cut a release`, `rolled out`

— in the context of one of these scopes:
- Feature (product code change, customer-facing)
- Customer (signed, renewed, expanded, escalation closed)
- Hire (offer accepted, started, departed)
- Infrastructure (system deployed, pipeline live, MCP server up)
- Board / leadership (memo sent, deck delivered)
- Customer-facing report (renewal report PR merged, official-scores PDF delivered)

### Do NOT append if

- Verb is hypothetical ("if we ship X by Friday").
- Scope is a personal task or a draft ("shipped a draft", "merged my own scratch branch").
- Item was previously logged in this month's Shipping Log (dedupe by title — string match against existing entries).
- Verb refers to someone else's work that Mo had no role in (Shipping Log is Mo-scoped achievements; team-wide shipping goes elsewhere).

### Destination

`Work/Chalktalk/Shipping Log.md` — append under the heading `## YYYY-MM <Month Name>`. Create the month section if it doesn't exist.

### Entry format

```markdown
- **YYYY-MM-DD** — <one-line description of what shipped>. [[Sessions/YYYY-MM/<session-log-name>]]
```

Newest entry at the top of the month section.

### Stub left in session log

None. The Shipping Log entry stands alone; the back-reference to the session log is the wikilink in the entry itself. The session log keeps its original 🟢 / "shipped" prose unchanged.

---

## (c) Brag-Worthy Moment

Appends an entry to `Personal/Brag Doc.md` under the current quarter section.

Apply the **Cold-Reader Test** (below) to every candidate. There is no default frequency in either direction — some periods produce many brag entries because rare things actually happened; others produce none because nothing exceptional occurred. Let the test decide each time.

### The Cold-Reader Test

A candidate passes only if it clears this bar:

> Imagine a stranger reads this single Brag Doc line in 2 years with zero context — no conversation history, no knowledge of the user, their team, or the situation. Would they think *"this person delivered something exceptional and I want to work with them"*? Or would they think *"this person seems thoughtful"*?

If the answer is "thoughtful," skip it. The bar is the first reaction, not the second.

### Filters in (extract)

- Shipped / closed / landed / secured outcomes with external impact (closed customer, secured funding, hired key person, won a deal under uncertainty)
- Hard calls under genuine uncertainty with measurable downstream results
- Recovery from a crisis where the alternative was real damage
- Codified something *others* now use (a system, doc, or process the team adopted)
- Rare leadership moments a non-insider would recognize as exceptional

### Filters out (do NOT extract)

- **Meta-cognition or self-correction** ("caught my own defensive framing", "stepped back and questioned X") — invisible to a cold reader
- **Iterative copy / design / planning refinement** — normal craftwork that produces a deliverable
- Routine work, even when done well ("ran the standup", "wrote good documentation")
- Receiving mentorship or feedback (growth journaling, not a brag)
- Failures or near-misses without resolution ("almost shipped a bug" — only brag-worthy if the user caught it AND the consequence of missing it was real)
- Anything that only makes sense to someone who was in the room
- Already logged this quarter — dedupe by substring match

### Destination

`Personal/Brag Doc.md` — append under the heading `## YYYY Q<N>` (e.g. `## 2026 Q2`). Create the quarter section if it doesn't exist.

### Entry format

```markdown
- **YYYY-MM-DD** — <one-line achievement, written in past tense, first person>. [[Sessions/YYYY-MM/<session-log-name>]]
```

Newest entry at the top.

### Stub left in session log

None. Brag Doc lives in `Personal/`; the session log keeps the original prose. Cross-link is via the wikilink in the Brag Doc entry.

---

## (d) New-Person Flag

Surfaces a confirmation prompt when the session log mentions a person who has no existing People note.

### Triggers

Session log mentions a name (proper noun, capitalized first + last, or capitalized first name in a context that implies a specific person — Slack handle, role mention, "talked to <name>") for whom **no file exists** at:

```
Work/Chalktalk/People/<Real Name>.md
```

Resolution rule: check exact filename match first; then check the org-chart YAML's `name-map.json`-style aliases (display_name, slack_handle, secondary names) if present. Only flag as new if no resolution path matches.

### Do NOT flag if

- Name resolves via the org-chart YAML alias map (different display name, same person).
- Name is a public figure / external party (vendor contact, journalist, founder of another company) unless Mo explicitly tracks them.
- Name is ambiguous (just a first name with no context) — leave alone, don't prompt.
- Session log explicitly says "external" or "not on team".

### Action

**Do NOT auto-create the People note.** Surface a prompt:

```
Create People note for <Name>? They were mentioned in this session but no file exists at Work/Chalktalk/People/<Name>.md.

Options:
1. Yes — create with org-chart YAML defaults (if on chart) or a stub frontmatter (if off-chart).
2. No — they're external / one-off / I track them elsewhere.
3. Alias — they're already in the vault under a different name (provide the existing filename).
```

Mo confirms. On `Yes`, create using `people-template.md` schema; populate from org-chart YAML if matched, otherwise stub frontmatter with `on_org_chart: false`.

### Stub left in session log

None. The mention in the session log is unchanged regardless of outcome. If a People note is created, the existing mention becomes a wikilink target retroactively (via Obsidian's link autocomplete on next edit).

---

## How extraction is invoked

**Step 4.5 of the session-end ritual.** Sequence:

1. Step 4 finishes — the session log is written to disk via the Write tool.
2. Step 4.5 begins. Re-read the session log in full.
3. Run all four extraction scans in parallel (decisions, shipping-log, brag-worthy, new-person).
4. Build a **single batched confirmation summary** in the terminal:

```
Extractions detected from this session:

DECISIONS (2):
1. "No YAML status fields in model registry" → Work/Chalktalk/Decisions/2026-05-08-no-yaml-status-fields-in-model-registry.md
2. "Use git log for verification" → Work/Chalktalk/Decisions/2026-05-08-git-log-verification-gate.md

SHIPPING LOG (1):
1. 🟢 Renewal report PR merged for Highline → append to Shipping Log.md under "2026-05 May"

BRAG-WORTHY (1):
1. "Pushed back on premature schema lock" → append to Personal/Brag Doc.md under "2026 Q2"

NEW PERSON FLAGS (1):
1. "Sarah Chen" mentioned but no Work/Chalktalk/People/Sarah Chen.md exists.
   Action? [Yes / No / Alias]

Approve all? [y/n/edit]
```

5. Wait for user confirmation. Accept `y` (apply all), `n` (apply none), or `edit` (walk through item-by-item).
6. On approval, apply each extraction:
   - Decisions: create the Decision note, replace the session-log bullet with a wikilink stub.
   - Shipping Log: prepend entry to the appropriate month section.
   - Brag Doc: prepend entry to the appropriate quarter section.
   - New-person: create People note (if `Yes`), do nothing (if `No`), or skip and note alias for next time (if `Alias`).
7. Print a one-line confirmation: `Applied N extractions: D decisions, S shipping entries, B brag entries, P people notes.`

### Constraints

- Never apply extractions without confirmation.
- Never duplicate content — extraction always replaces inline session-log content with a wikilink, or appends to an external doc with a session-log back-reference.
- If an extraction would create a file that already exists (e.g. a Decision note for that date+slug already exists), surface as a conflict in the confirmation prompt — don't silently overwrite.
- Extraction failures are non-fatal — log them, continue with the rest of the batch.

## Cross-references

- Decision schema → `decision-template.md`
- People schema (for new-person flags) → `people-template.md`
- Org-chart YAML used to resolve aliases → `org-chart-source.md`
- Source-logging is a sibling extraction handled separately → `source-logging-rules.md`
