# Decision Note Template

Schema and section layout for `Work/Chalktalk/Decisions/YYYY-MM-DD-<slug>.md`. One file per consequential decision. Decisions live in their own folder so they survive session-log rotation and form a queryable chronology.

## Filename Convention

`Work/Chalktalk/Decisions/YYYY-MM-DD-<slug>.md` — ISO date, hyphen, kebab-case slug derived from the decision. Example: `Work/Chalktalk/Decisions/2026-05-08-no-yaml-status-fields-in-model-registry.md`.

The slug should be a noun phrase summarizing the decision, not a verb. `2026-05-08-no-yaml-status-fields...` not `2026-05-08-decided-against-yaml-status...`.

## Frontmatter (exact field order)

```yaml
---
type: decision
date: 2026-05-08
status: accepted
owner: "[[Work/Chalktalk/People/Mo Arbaji]]"
stakeholders:
  - "[[Work/Chalktalk/People/Ciaran Hollywood]]"
  - "[[Work/Chalktalk/People/Eric Du]]"
supersedes:
tags: [decision, model-registry]
---
```

### Field rules

- `type: decision` — never change.
- `date` — ISO date the decision was made (not when the discussion started).
- `status` — one of:
  - `proposed` — under discussion, not yet binding
  - `accepted` — currently in force
  - `superseded` — replaced by a later decision (set `supersedes` on the new one to point back here, then flip this one to `superseded`)
  - `deprecated` — no longer relevant, but not actively replaced
- `owner` — wikilink to the single person accountable for the decision.
- `stakeholders` — list of wikilinks. People who were consulted or are affected. Include the owner here too — redundant but explicit.
- `supersedes` — optional wikilink to a prior decision this one replaces. Empty if this is a fresh decision.
- `tags` — always include `decision`. Add domain tags (`model-registry`, `hiring`, `customer`, etc.).

## Section Layout (in this order)

```markdown
# <Decision Title>

## Context

## Options Considered

## Chosen

## Reasoning

## Consequences

## Source Session
```

## Section semantics

### Context

Why this decision needed to be made. The forcing function. 2–4 sentences. Link to relevant prior decisions, session logs, or external sources.

### Options Considered

Numbered list of options. Each entry: name, one-sentence description, key trade-off. Even if only one option was seriously considered, write down the alternatives that were ruled out — future-self needs the contrast.

```markdown
## Options Considered

1. **Add `verified_by` / `verified_date` / `verification_status` fields to the YAML.** Trade-off: explicit at the file level, but pollutes LLM context with defensive "check both" patterns.
2. **Use git log + empty `review:` commits as the verification gate.** Trade-off: requires reading git history but keeps the YAML clean.
3. **Sidecar verification log.** Trade-off: a third source of truth — drift risk.
```

### Chosen

State the chosen option in one sentence. Bold the option name.

```markdown
## Chosen

**Option 2** — git log + empty `review:` commits.
```

### Reasoning

The why. Bullet list. Each bullet a single load-bearing reason. Reference any constraints, principles, or prior lessons (link to `tasks/lessons.md` entries via path).

### Consequences

What this decision implies for follow-on work. Includes things that become possible, things that become forbidden, things that need to be communicated, and watch-points.

```markdown
## Consequences

- All review activity must flow through commits with `review:` prefix; no GUI-only sign-offs.
- Need to update `model-registry-reviewer` skill to emit empty review commits (not edit YAML).
- Watch: if engineers stop using `review:` prefix consistently, this decision degrades silently.
```

### Source Session

Wikilink to the session log where the decision originated. Required. This is how the session log and the decision note stay connected after extraction.

```markdown
## Source Session

- [[Sessions/2026-05/2026-05-08-model-registry-yaml-cleanup]]
```

## When to create a Decision note vs leave it inline

The session-end ritual flags decisions for extraction (see `extraction-rules.md`). Default: leave decisions inline in the session log's `## Key Decisions` section. Promote to a Decision note only when at least one of these is true:

- **Multi-week relevance** — the decision will still matter 2+ weeks from now.
- **Policy-shaped** — establishes a rule that applies beyond a single project.
- **Affects multiple people** — at least one stakeholder besides the owner.
- **Supersedes a prior approach** — replaces something previously codified.
- **Phrased as a binding choice** — session log uses "Decided to X", "Going with Y", "Chose A over B for Z reason".

If none apply, the decision stays inline. Don't create Decision notes for ephemeral choices ("decided to use Sonnet for this one query") — that's noise.

## Lifecycle: superseding a decision

When a new decision replaces an older one:

1. Create the new decision note with `supersedes: "[[Work/Chalktalk/Decisions/<old-decision-file>]]"`.
2. Edit the old decision note's frontmatter: flip `status: accepted` to `status: superseded`.
3. In the old note, append a `## Superseded By` section linking forward to the new decision.

This bidirectional link makes the chronology navigable in both directions.

## Cross-references

- Extraction trigger and decision-extraction rules → `extraction-rules.md`
- Owner / stakeholders link to → `people-template.md`
- Action items in 1:1 notes can promote to decisions when scope expands → `one-on-one-template.md`
