---
description: How to adopt obsidian-memory's org-and-perf layer for your own company. Walks through populating your vault with org-specific data (org chart YAML, People notes, Competency notes, Values, Shipping Log, Brag Doc) so the skill's session-end ritual + invokable skills (board-update, investor-update, quarterly-review, employee-review) have content to operate on.
---

# Adopting This Skill for Your Own Org

## Overview

`obsidian-memory` ships **generic primitives** — templates, extraction rules, vault layout conventions, and four invokable skills (`board-update`, `investor-update`, `quarterly-review`, `employee-review`). The skill itself is the same for every adopter.

What makes the skill *yours* is **content you populate into your private Obsidian vault**: your org chart, your direct reports as People notes, your company's role scorecards mirrored into Competency notes, your Values, your Shipping Log, your Brag Doc.

The split:

- **Public** — this skill repo. Templates, extraction rules, the four invokable skills. Safe to share.
- **Private** — your Obsidian vault. People notes, 1:1 notes, Decisions, Reviews, Values content, Shipping Log entries, Brag Doc entries, your `org-chart.yaml`. Never committed to a public skill repo.

Once your vault is seeded, the session-end ritual + the four invokable skills work without any further configuration.

---

## One-time setup

### Step 1. Decide your `<YourOrg>` folder name

The skill uses `<YourOrg>/` as the placeholder root for org-scoped notes. Pick what fits your vault structure:

- `Work/Acme/` — if you compartmentalize work vs personal in one vault.
- `Acme/` — if the vault is work-only.
- `/` (vault root) — if you want People, Competencies, etc. at the top level.

Whichever you choose, use it consistently. The session-end ritual and the four invokable skills resolve paths relative to this root.

### Step 2. Scaffold the structure

Create the folder skeleton and the two top-level files. Adjust `<YourOrg>` to whatever you picked in Step 1:

```bash
VAULT="$HOME/Documents/$(cat ~/.claude/obsidian-vault-name)"
ORG="<YourOrg>"  # e.g. "Work/Acme"

mkdir -p "$VAULT/$ORG/People"
mkdir -p "$VAULT/$ORG/Departments"
mkdir -p "$VAULT/$ORG/Competencies"
mkdir -p "$VAULT/$ORG/1-on-1s"
mkdir -p "$VAULT/$ORG/Decisions"
mkdir -p "$VAULT/$ORG/Reviews"
mkdir -p "$VAULT/$ORG/Board Updates"
mkdir -p "$VAULT/$ORG/Investor Updates"
mkdir -p "$VAULT/Personal/Quarterly Reviews"

touch "$VAULT/$ORG/Values.md"
touch "$VAULT/$ORG/Shipping Log.md"
touch "$VAULT/Personal/Brag Doc.md"
```

The `Personal/` tree lives outside `<YourOrg>/` because Brag Doc and Quarterly Reviews are user-scoped, not org-scoped — they follow you across employers.

### Step 3. Populate `Values.md`

Open `<YourOrg>/Values.md`. Mirror your company's values doc/page into it. One section heading per value. Suggested structure:

```markdown
# <Your Company> Values

## <Value 1 name>

<one-paragraph definition, lifted from your company's source>

## <Value 2 name>

...
```

Common value names you might see across companies: "Bias to Action", "Customer Focus", "Ownership", "Transparency", "Excellence", "Curiosity". Use whatever your company actually has — these are just illustrative.

`Values.md` is referenced by `competency-template.md` (every Competency has a `## Related values` section that wikilinks here) and by `employee-review` (cites a concrete instance per value during review drafts).

### Step 4. Create your org-chart YAML

In a private location outside the public skill repo, create `org-chart.yaml`. Common locations: `~/Desktop/tasks/org-chart.yaml`, `~/Documents/org-chart.yaml`, or a private notes repo.

Use the schema in `org-chart-source.md`. Minimal example:

```yaml
last_refreshed: 2026-05-08
chart_source: "Notion org chart, screenshot 2026-05-07"

people:
  - real_name: Alex Morgan
    display_name: Alex
    slack_handle: alex
    canonical_email: alex@example.com
    role: Staff Engineer
    department: Engineering
    sub_team: Platform
    manager: Jordan Smith
    direct_reports:
      - Riley Chen
    on_org_chart: true
    status: active

  - real_name: Riley Chen
    ...
```

The full field rules and refresh flow are in `org-chart-source.md`. Read that file before doing the first refresh.

### Step 5. Seed People notes from the YAML

You can do this manually using `people-template.md`, or let Claude do it:

```
"Seed my People notes from <absolute path to org-chart.yaml>. Use the schema in
references/people-template.md. One file per person under <YourOrg>/People/.
Don't overwrite existing files — show me what you'd create first."
```

Each People note gets the org-chart-authoritative fields populated (`role`, `department`, `manager`, `direct_reports`). The manually-maintained sections (`Profile`, `Working Style`, `Strengths`, `Areas of Growth`, `Notes`) start empty — you fill those over time.

### Step 6. Mirror your role scorecards into Competency notes

If your company has role scorecards (in Notion, Lattice, a Google Doc, etc.), each role-level rubric becomes one Competency note under `<YourOrg>/Competencies/`. You can do this manually using `competency-template.md`, or ask Claude:

```
"Pull my Engineering scorecard from <Notion URL or file path> and mirror each
competency into a Competency note under <YourOrg>/Competencies/Engineering/.
Use the schema in references/competency-template.md."
```

Each Competency note describes one competency, with concrete examples per role level (Junior / Mid / Senior / Staff or whatever your framework defines), and links back to relevant entries in `Values.md`.

The `Evidence` section on each Competency note is **backlink-driven** — it fills in automatically as session logs, 1:1 notes, and Decisions wikilink to the competency.

---

## Optional: wire up the SessionStart hook and QMD semantic search

Both are independent token-cost optimizations. Skill works without them.

- **SessionStart hook** — emits structured vault context procedurally at session start, replacing 15-20K tokens of LLM-driven file reads with about 5-6K tokens of shell output. Setup: `references/session-start-hook.md`.
- **QMD semantic search MCP** — registers `mcp__qmd__query` for chunked semantic recall over your vault. Falls back to `obsidian search:context` if not installed. Setup: `references/qmd-setup.md`.

---

## Ongoing

Keep the vault in sync as your org changes:

- **Org chart changes (reorg, hire wave, departure)** — edit `org-chart.yaml`, then re-run the people-seed flow. The agent will diff and propose creates / updates / mark-departed actions. See `org-chart-source.md` for the refresh flow.
- **New hires mentioned in sessions** — the session-end ritual's new-person flag (see `extraction-rules.md`) surfaces a confirmation prompt when a session log mentions a name with no existing People note. Confirm `Yes` to create.
- **1:1 capture** — currently manual. Write a 1:1 note after each meeting using `one-on-one-template.md`. The future automated import flow is specced in `future-1on1-import.md` but not implemented.
- **Decisions** — flagged for extraction by the session-end ritual when their phrasing matches the decision triggers in `extraction-rules.md`. Confirm to promote inline session-log decisions to standalone Decision notes.
- **Shipping Log / Brag Doc** — append automatically by the session-end ritual when triggers match (see `extraction-rules.md`).

---

## What's private vs public

| Lives in your vault (private — never committed to a public skill repo) | Lives in this skill repo (public) |
|---|---|
| `<YourOrg>/People/*.md` (all People notes) | `references/people-template.md` (the schema) |
| `<YourOrg>/Competencies/*.md` (your scorecard mirror) | `references/competency-template.md` |
| `<YourOrg>/1-on-1s/*.md` (every 1:1 note) | `references/one-on-one-template.md` |
| `<YourOrg>/Decisions/*.md` | `references/decision-template.md` |
| `<YourOrg>/Reviews/*` | `skills/employee-review/SKILL.md` |
| `<YourOrg>/Values.md` (your company's values content) | `references/extraction-rules.md` |
| `<YourOrg>/Shipping Log.md` | `references/org-chart-source.md` (the schema, not your YAML) |
| `Personal/Brag Doc.md` | `references/future-1on1-import.md` |
| `Personal/Quarterly Reviews/*` | `references/adopting-this-skill.md` (this file) |
| `org-chart.yaml` (your private YAML) | `skills/obsidian-memory/SKILL.md` (the session-end ritual) |
| `Sessions/*` (session logs) | `skills/board-update/SKILL.md` |
|  | `skills/investor-update/SKILL.md` |
|  | `skills/quarterly-review/SKILL.md` |

If you fork this skill repo, never commit anything from the left column. Keep the vault and the skill repo in separate directories — there's no need for the skill repo to know about your vault contents.

---

## Cross-references

- People note schema → `people-template.md`
- Competency note schema → `competency-template.md`
- 1:1 note schema → `one-on-one-template.md`
- Decision note schema → `decision-template.md`
- Session-end extraction triggers → `extraction-rules.md`
- Org-chart YAML schema and refresh flow → `org-chart-source.md`
- Future automated 1:1 import (spec only) → `future-1on1-import.md`
- SessionStart hook setup → `session-start-hook.md`
- QMD semantic search setup → `qmd-setup.md`
