# 1:1 Note Template

Schema and section layout for `Work/Chalktalk/1-on-1s/<First Name> YYYY-MM-DD.md`. One file per 1:1 instance.

## Filename Convention

`Work/Chalktalk/1-on-1s/<First Name> YYYY-MM-DD.md` — first name only, space, ISO date. Example: `Work/Chalktalk/1-on-1s/Ciaran 2026-05-08.md`.

If two reports share a first name, use `<First Last> YYYY-MM-DD.md` instead. The `person` frontmatter field disambiguates either way; the filename is for human scanning.

## Frontmatter (exact field order)

```yaml
---
type: 1on1
date: 2026-05-08
person: "[[Work/Chalktalk/People/Ciaran Hollywood]]"
duration_min: 30
format: Zoom
recorded: true
recording: https://zoom.us/rec/share/...
tags: [1on1, engineering]
---
```

### Field rules

- `type: 1on1` — never change.
- `date` — ISO date the 1:1 happened.
- `person` — wikilink to the People note. Required. The backlink from this field is what populates the person's `## Recent 1:1s` section (see `people-template.md`).
- `duration_min` — integer, optional. Default omitted if unknown.
- `format` — one of `Zoom`, `In-person`, `Async` (Slack DM, Loom, doc-comment thread). Other values discouraged.
- `recorded` — `true` / `false`. If `true`, add a `recording` field with the source URL (Zoom cloud link, Oliv summary URL, etc.). The future import flow (see `future-1on1-import.md`) populates these from transcripts automatically.
- `tags` — always include `1on1`. Add the person's department tag for filterability (`engineering`, `cs`, etc.).

## Section Layout (in this order)

```markdown
# 1:1 with <First Name> — YYYY-MM-DD

## Key Takeaways

## Action Items (mine)

## Action Items (theirs)

## Notable Quotes

## Open Questions

## Follow-up Date
```

## Section semantics

### Key Takeaways

3–6 bullets. The substance of the conversation, not the agenda. Written for Mo's future self — what was learned, what changed, what surfaced. Reference competencies via wikilinks where applicable so the backlink propagates to `Work/Chalktalk/Competencies/<X>.md#Evidence`.

```markdown
## Key Takeaways

- Ciaran is feeling stretched between platform work and customer-facing requests; surfaces a need for clearer triage. Relates to [[Work/Chalktalk/Competencies/Prioritization]].
- Pushed back on the proposed schema lock for run traces — wants a 2-week soak first.
```

### Action Items (mine) / (theirs)

Bullet list of Obsidian tasks (`- [ ] ...`). Use Obsidian's task syntax so they aggregate in dataview / task panes.

```markdown
## Action Items (mine)

- [ ] Send Ciaran the Notion page on triage rubric by 2026-05-12
- [ ] Loop in Eric on the schema-lock decision

## Action Items (theirs)

- [ ] Ciaran to draft the 2-week soak plan by 2026-05-15
```

The future import flow (see `future-1on1-import.md`) infers action items from transcripts and emits them as unchecked tasks here.

### Notable Quotes

Verbatim quotes worth preserving. Each quote attributed and dated implicitly via the file. Useful for performance reviews and `Personal/Brag Doc.md` extractions.

```markdown
## Notable Quotes

> "I'd rather we ship the wrong thing fast and learn than over-spec for two weeks." — Ciaran
```

### Open Questions

Things that surfaced and weren't resolved. Carry forward to the next 1:1 by linking from the next 1:1's `## Key Takeaways` to the previous `## Open Questions`.

### Follow-up Date

Single line: the date the next 1:1 is scheduled (or "TBD" if unscheduled). Useful for cadence audits — surfaces drift in 1:1 cadence.

## Backlink mechanics

Because the frontmatter `person` field wikilinks to the People note, the People note's `## Recent 1:1s` section automatically lists this file in Obsidian's backlinks panel. Never manually add 1:1 entries to the People note — let the backlink graph do it (see `people-template.md`).

## Future automation

1:1 capture is currently **not implemented**. Mo's 1:1s are recorded in Zoom (cloud) and summarized by Oliv AI. The intended flow — auto-detecting new transcripts, generating 1:1 notes per this template, redacting sensitive content, leaving action items as unchecked Obsidian tasks — is specced in `future-1on1-import.md`.

Until that lands, 1:1 notes are written manually after the meeting using this template.

## Cross-references

- Person frontmatter field links to → `people-template.md`
- Competency wikilinks in Key Takeaways propagate to → `competency-template.md`
- Action items can be promoted to decisions when scope expands → `decision-template.md`
- Future automation spec → `future-1on1-import.md`
