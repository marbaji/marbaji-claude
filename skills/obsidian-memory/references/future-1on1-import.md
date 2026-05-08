# Future 1:1 Import Flow (Spec — Not Implemented)

This is a forward-looking spec. **Nothing in this file is implemented yet.** Mo's 1:1 capture today is fully manual: after a meeting, he writes a 1:1 note by hand using `one-on-one-template.md`.

This document records the design constraints and open questions for the future automated flow so the implementation effort doesn't restart from zero.

## Current state (as of 2026-05-08)

- 1:1s are recorded in **Zoom** (cloud recordings, accessible via Mo's Zoom account).
- 1:1s are auto-summarized by **Oliv AI** (https://oliv.ai), which generates structured meeting notes.
- Neither feed lands in the vault automatically. Both require manual extraction.
- Manually-written 1:1 notes follow `one-on-one-template.md` schema.
- 1:1 frequency is variable — typically weekly per direct report, biweekly with peer leads.

## Intended flow

When implemented, the flow should:

1. **Detect new transcripts** in a designated source (mechanism TBD — see open questions).
2. **Parse each transcript** to extract:
   - Meeting date and duration.
   - Participants (resolved to People notes via `org-chart-source.md` aliases).
   - Key takeaways (3–6 bullets).
   - Action items, attributed to "mine" (Mo) or "theirs" (the report) based on speaker.
   - Notable quotes — verbatim, attributed.
   - Open questions (anything explicitly unresolved).
3. **Generate a 1:1 note** at `Work/Chalktalk/1-on-1s/<First Name> YYYY-MM-DD.md` using the schema in `one-on-one-template.md`. Set `recorded: true` and populate the `recording` field with the source URL.
4. **Link to the participant's People note** via the `person` frontmatter field. The backlink populates the People note's `## Recent 1:1s` section automatically.
5. **Emit action items as Obsidian tasks** (`- [ ] ...`) — never pre-checked.
6. **Surface a confirmation prompt** before writing — Mo reviews the parsed output and approves / edits / rejects.

## Open design questions

### 1. Data source detection

Three plausible mechanisms, none chosen:

- **Drive sync.** Zoom can auto-upload recordings to Google Drive. The flow watches a designated Drive folder via `mcp__claude_ai_Google_Drive__search_files` and reads new files. **Pro:** no local infra. **Con:** depends on Drive sync being healthy; transcripts may lag uploads by hours.
- **Local download.** Mo periodically pulls Zoom recordings to `~/Downloads/zoom-1on1s/`. The flow scans the directory on session start. **Pro:** simple, no API quota. **Con:** Mo has to remember to download.
- **Oliv API integration.** Oliv exposes summaries via API. The flow polls for new summaries. **Pro:** structured input (Oliv has already parsed). **Con:** vendor coupling; auth scope unknown.

**Decision deferred.** The first implementation should support whichever path Mo's already using when he asks for this to be built — match the existing workflow rather than impose a new one.

### 2. Automatic vs explicit invocation

Two modes:

- **Automatic.** Session start runs a quick check ("any new transcripts since last session?") and surfaces a prompt if found. Low ceremony, but adds latency to every session start.
- **Explicit.** Mo runs `/import-1on1s` (or similar) when he wants to process the backlog. No session-start cost, but requires manual trigger.

**Lean toward explicit** — session start is already heavy; adding a Drive/local scan to it pushes startup time past acceptable. Explicit invocation also makes failures obvious instead of silent.

### 3. Multi-person meetings

A 1:1 has exactly one report. Sometimes a "1:1" actually has multiple participants (e.g. a 3-person sync, an interview panel, a debug huddle). The schema in `one-on-one-template.md` assumes one `person`.

Options:

- **Filter out multi-person meetings.** Detect via Zoom participant count > 2 and skip. Surface as "skipped — N-person meeting" in the confirmation prompt.
- **Promote to a different note type.** Multi-person syncs become `Work/Chalktalk/Meetings/YYYY-MM-DD-<topic>.md` with a different schema. Action items still attribute to specific people.

**Lean toward filter-and-skip for v1.** Multi-person meeting capture is a separate problem; don't entangle it with 1:1 import.

### 4. Sensitive content redaction

1:1s sometimes include:

- Comp discussions (numbers, equity).
- Health / personal hardship.
- Performance concerns about other team members (Mo's report complaining about a peer).
- Customer secrets shared in confidence.

The vault is local but not encrypted at rest. Mo's threat model is "what if someone shoulder-surfs, or what if I share my screen mid-vault-search."

Options:

- **Heuristic redaction.** Regex / keyword detection (`comp`, `salary`, `equity`, `medical`, `mental health`) flags content for redaction. Replace with `[REDACTED — see source recording]`.
- **LLM-based redaction.** Pass each section through a model with instructions to redact sensitive disclosures. Higher quality, higher token cost.
- **Whole-section gating.** If any redaction trigger fires in a section, omit the whole section from the note and leave a stub: "Sensitive content present — see source recording at <url>."
- **Manual review.** No automatic redaction; the confirmation prompt forces Mo to read every line before writing.

**Lean toward LLM-based redaction + manual review as final gate.** Heuristics will under-redact (miss euphemisms) and over-redact (flag innocuous mentions). Manual review on a parsed output is fast.

### 5. Transcript-quality fallbacks

Zoom auto-transcripts are imperfect (miss-named speakers, dropped words, technical-term garbling). Oliv summaries are higher quality but lossy.

Options:

- **Prefer Oliv when available, fall back to Zoom transcript.** Oliv's structured output makes parsing easier; the raw transcript is the backup for verification.
- **Ingest both, pass to LLM with both as context.** Higher fidelity, higher cost.

**Lean toward Oliv-primary, Zoom-fallback** — match the actual quality difference Mo experiences.

## What's not changing

- The 1:1 note schema (`one-on-one-template.md`) is stable. The import flow conforms to it; the schema doesn't change to accommodate the importer.
- People notes' `## Recent 1:1s` section stays backlink-driven (see `people-template.md`). The importer never writes there directly.
- Action items remain Obsidian tasks (`- [ ] ...`). The importer never pre-checks them.

## Implementation triggers

This spec becomes implementation work when:

- Mo explicitly asks for it (`"build the 1:1 import flow"`).
- Mo's 1:1 backlog reaches a point where manual capture is being skipped — surfacing as gaps in the People notes' `## Recent 1:1s` sections relative to known 1:1 cadence.
- A vault-lint check (see `vault-lint-rules.md`) is added that detects 1:1-cadence drift, and that lint flags > 4 weeks without a note for an active report.

Until then, this file is forward-looking documentation only.

## Cross-references

- Manual 1:1 schema (the target output format) → `one-on-one-template.md`
- Person resolution / alias map for participant mapping → `org-chart-source.md`
- People note backlink mechanics → `people-template.md`
