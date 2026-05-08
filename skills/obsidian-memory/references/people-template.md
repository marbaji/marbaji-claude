# People Note Template

Schema and section layout for `Work/Chalktalk/People/<Name>.md`. Use this when the org-chart seed creates a new note, when a new-person flag (see `extraction-rules.md`) is confirmed, or when manually adding someone the org chart missed.

## Filename Convention

`Work/Chalktalk/People/<Real Name>.md` — title case, spaces preserved, no slug. Example: `Work/Chalktalk/People/Ciaran Hollywood.md`.

If two people share a first name, the file uses the full real name (the org-chart YAML's `real_name` field) — never abbreviate.

## Frontmatter (exact field order)

```yaml
---
type: person
created: YYYY-MM-DD
slack_user_id: U0XXXXXXXX
slack_handle: ciaran
real_name: Ciaran Hollywood
display_name: Ciaran
canonical_email: ciaran@chalktalk.academy
secondary_email:
github_handle: pending
role: Senior Engineer
slack_title: Senior Engineer @ ChalkTalk
department: Engineering
sub_team: Platform
manager: "[[Work/Chalktalk/People/<Manager Name>]]"
direct_reports: []
timezone: America/New_York
joined: 2024-01-15
location: New York, NY
on_org_chart: true
status: active
tags: [person, engineering]
---
```

### Field rules

- `type: person` — never change.
- `created` — date the note was first written, not when the person joined.
- `slack_user_id` / `slack_handle` / `real_name` / `display_name` — pulled from Slack via `mcp__slack__users_search`. If unknown, leave empty (don't guess).
- `canonical_email` — the work email. `secondary_email` for personal/forwarding addresses; usually empty.
- `github_handle` — default `pending`. Only fill once verified against an actual GitHub profile (don't guess from `slack_handle`).
- `role` — **org-chart authoritative**. Comes from `~/Desktop/Claude Code/tasks/obsidian-people-seed-org-chart.yaml` (see `org-chart-source.md`). If the YAML and Slack disagree, the YAML wins.
- `slack_title` — Slack self-reported title. Cosmetic. Often differs from `role` (e.g. self-aggrandized titles, stale titles after promotion). Keep both.
- `department` / `sub_team` — from org chart YAML.
- `manager` — wikilink to another People note. The org-chart seed populates this; manual edits should keep the wikilink form.
- `direct_reports` — list of wikilinks. Maintained by the seed flow; do not hand-edit unless the chart changes.
- `on_org_chart: true` for anyone present in the YAML. `false` for contractors, advisors, ex-employees, or people Mo tracks who aren't on the chart.
- `status` — `active` (default), `on_leave`, `departed`. Never delete a People note when someone leaves; flip status.
- `tags` — always include `person`. Add `engineering`, `customer-success`, `leadership`, etc. as helpful.

## Section Layout (in this order)

```markdown
# <Real Name>

## Profile

## Working Style

## Strengths

## Areas of Growth

## Recent 1:1s

## Competency Evidence

## Recent Interactions

## Notes
```

## Section semantics

### Profile

Free-form prose. Background, how Mo met them, role history at ChalkTalk, anything contextual that doesn't fit the frontmatter. Manually maintained. The org-chart seed leaves this empty.

### Working Style

Manually maintained. How they communicate (async vs sync, DM vs channel, Slack vs Loom), meeting cadence, escalation patterns, decision-making style. Update opportunistically — never auto-filled.

### Strengths

Manually maintained. Bullet list. What they're known for. Short phrases, not paragraphs. Update when Mo notices a pattern.

### Areas of Growth

Manually maintained. Bullet list. Sensitive — written for Mo's eyes. Pair each item with the most recent supporting observation when possible. Never auto-filled.

### Recent 1:1s

**Backlink-driven.** Do not hand-edit. Obsidian's built-in backlinks panel surfaces every `1-on-1s/<First Name> YYYY-MM-DD.md` whose frontmatter `person` field wikilinks to this note. The session-end ritual never writes here.

If Mo wants a curated subset (e.g. "the three most consequential 1:1s of the year"), put that in `## Notes` instead — `Recent 1:1s` is exhaustive by construction.

### Competency Evidence

**Backlink-driven.** Do not hand-edit. Surfaces every Competency note (see `competency-template.md`) that wikilinks to this person in its `## Evidence` section. As Competency evidence accumulates from session logs and 1:1s, this section grows automatically via backlinks.

### Recent Interactions

**Auto-filled by the session-end ritual.** When a session log mentions this person by name, the ritual appends a one-line entry:

```markdown
- [[Sessions/2026-05/2026-05-08-renewal-storytelling]] — flagged YAML status-field pollution; pushed back on adding `verified_by`
```

Format: `- [[Sessions/...]] — <one-line summary of the interaction>`. Newest at the top. Cap at ~30 entries — older entries roll into `## Notes` as a compressed prose summary every quarter (manual cleanup).

Never edit this section by hand during a session. The session-end ritual owns it.

### Notes

Catch-all. Quotes, anecdotes, things Mo wants to remember. Manually maintained. Long-lived — the place where compressed prose summaries from `Recent Interactions` end up when that section is rolled over.

## Cross-references

- Org-chart YAML schema and refresh flow → `org-chart-source.md`
- Extraction triggers (new-person flag, Recent Interactions append) → `extraction-rules.md`
- 1:1 note schema (linked via Recent 1:1s backlinks) → `one-on-one-template.md`
- Competency note schema (linked via Competency Evidence backlinks) → `competency-template.md`
