# Competency Note Template

Schema and section layout for `Work/Chalktalk/Competencies/<Competency Name>.md`. Competency notes are role-scoped rubric entries — each describes a single competency from ChalkTalk's Notion-defined career framework, with concrete examples per level and accumulated evidence backlinks.

## Filename Convention

`Work/Chalktalk/Competencies/<Competency Name>.md` — title case, spaces preserved. Example: `Work/Chalktalk/Competencies/Technical Judgment.md`.

If the same competency name applies to multiple roles (e.g., "Communication" for both Engineering and CS), suffix with the role: `Communication (Engineering).md`, `Communication (CS).md`.

## Frontmatter (exact field order)

```yaml
---
type: competency
role: Engineer
department: Engineering
description: Ability to make sound technical decisions under uncertainty, weighing trade-offs across timeline, complexity, and long-term maintainability.
notion_source: https://www.notion.so/chalktalk/Engineering-Career-Framework-...
created: YYYY-MM-DD
tags: [competency, engineering]
---
```

### Field rules

- `type: competency` — never change.
- `role` — the role this competency applies to (e.g. `Engineer`, `Senior Engineer`, `Account Manager`). Use the canonical role title from the org-chart YAML.
- `department` — `Engineering`, `Customer Success`, `Sales`, `Product`, `Operations`, `Leadership`.
- `description` — one or two sentences. Lifted verbatim from the Notion source when possible.
- `notion_source` — full URL to the Notion page defining this competency. Required. If the competency was extracted from a different source, document where in the description.
- `created` — when the note was first written.
- `tags` — always include `competency`. Add the department tag (`engineering`, `cs`, etc.).

## Section Layout (in this order)

```markdown
# <Competency Name>

## Definition

## What "Junior" looks like

## What "Mid" looks like

## What "Senior" looks like

## What "Staff" looks like

## Related values

## Evidence

## See also
```

## Section semantics

### Definition

Expand the frontmatter `description`. Cite the Notion source. Include the rationale for why this competency exists in ChalkTalk's framework. Manually maintained.

### What "<Level>" looks like

One section per role level the framework defines for this department. Engineering uses Junior / Mid / Senior / Staff. Customer Success uses CSM / Senior CSM / Lead. Match what Notion has — don't invent levels.

Each section is a bullet list of concrete observable behaviors. Short imperative phrases. Pulled from the Notion page first, augmented with examples Mo has observed.

```markdown
## What "Senior" looks like

- Decomposes ambiguous problems into a sequence of small verifiable steps before writing code.
- Pushes back on under-specified asks; reframes the question before answering.
- Reviews other engineers' designs and identifies risks they missed.
```

### Related values

Wikilinks to sections of `Work/Chalktalk/Values.md`. Every competency should ladder back to at least one company value. If no value clearly maps, leave a note: "No direct value mapping — flag for framework review."

```markdown
## Related values

- [[Work/Chalktalk/Values#Bias to Action]]
- [[Work/Chalktalk/Values#Customer Obsession]]
```

### Evidence

**Backlink-driven. Never hand-edit this section.** Obsidian's built-in backlinks panel surfaces every note that wikilinks to this competency. As session logs, 1:1 notes, and decision notes mention this competency by wikilink, they appear here automatically.

Manually adding entries here defeats the backlink-as-source-of-truth principle and creates drift. If Mo wants a curated highlight reel, put it in `## See also` as wikilinks to the most consequential evidence — but the raw evidence stream stays backlink-only.

The session-end ritual does not write here directly. It writes to session logs and 1:1 notes; Obsidian's backlink graph propagates.

### See also

Curated wikilinks. Other competency notes that pair with this one, the relevant Notion page, related decision notes, or canonical session logs that exemplify the competency. Manually maintained.

## How competency notes get linked

Three paths feed `## Evidence`:

1. **Session logs** — when a session log narrates a moment that exemplifies a competency, include a wikilink to the competency note in the relevant bullet (e.g., "Pushed back on premature schema lock — exhibited [[Work/Chalktalk/Competencies/Technical Judgment]]"). The session-end ritual handles this when it spots competency-evidence patterns (see `extraction-rules.md`).
2. **1:1 notes** — when Mo discusses a report's growth area or strength, link to the relevant competency in the 1:1's section.
3. **Decision notes** — when a decision was driven by demonstrating or violating a competency.

## Cross-references

- People notes link to competencies via `## Competency Evidence` (also backlink-driven) → `people-template.md`
- 1:1 notes accumulate competency mentions → `one-on-one-template.md`
- Extraction triggers for competency mentions → `extraction-rules.md`
