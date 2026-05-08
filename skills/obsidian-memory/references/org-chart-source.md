# Org Chart Source

The canonical source of truth for People notes is a YAML file Mo maintains by hand from a pinned org-chart image:

```
~/Desktop/Claude Code/tasks/obsidian-people-seed-org-chart.yaml
```

Absolute path: `/Users/mohannadarbaji/Desktop/Claude Code/tasks/obsidian-people-seed-org-chart.yaml`.

This file is the single authority for the `role`, `department`, `sub_team`, `manager`, and `direct_reports` fields in every `Work/Chalktalk/People/<Name>.md` note. When the YAML and Slack disagree, the YAML wins (Slack titles are self-reported and often stale).

## When to refresh

Refresh whenever Mo shares a new pinned org-chart image — typically after a reorg, a hire wave, or a departure. Cadence is irregular, not scheduled.

The YAML does **not** auto-sync from Slack, HubSpot, or any HR system. It's manually edited based on the chart Mo pins. Trying to derive it from Slack workspace data is the wrong move — Slack lacks reporting structure.

## Refresh flow

When Mo says "the org chart updated" or shares a new chart image:

1. **Mo provides the image.** Either an `Attachment` in the conversation or a path on disk (`~/Desktop/...png`, `~/Downloads/...jpg`).
2. **Read the image.** Use the Read tool on the image path. Extract every name, role, manager relationship, and team grouping visible in the chart.
3. **Diff against the existing YAML.** Compare the parsed chart to the current `obsidian-people-seed-org-chart.yaml`:
   - **Added** people — names in the chart but not in the YAML.
   - **Removed** people — names in the YAML but not in the chart.
   - **Changed** roles / managers / departments — same name, different fields.
4. **Diff against existing People notes.** For each YAML entry, check whether `Work/Chalktalk/People/<Real Name>.md` exists.
5. **Build a confirmation summary.** Present the diff as a single batched prompt:

```
Org chart refresh — proposed changes:

ADDED (3):
1. Sarah Chen — Senior Engineer, Platform, reports to Ciaran Hollywood
2. ...

REMOVED (1):
1. Alex Rivera — was Mid Engineer, Platform. Departed?

CHANGED (2):
1. Ciaran Hollywood: role "Senior Engineer" → "Staff Engineer"
2. ...

PEOPLE NOTES TO CREATE (3):
- Work/Chalktalk/People/Sarah Chen.md
- ...

PEOPLE NOTES TO UPDATE (2):
- Work/Chalktalk/People/Ciaran Hollywood.md (role + department)
- ...

PEOPLE NOTES TO MARK DEPARTED (1):
- Work/Chalktalk/People/Alex Rivera.md (status: active → departed)

Apply? [y/n/edit]
```

6. **Wait for confirmation.** Mo can confirm all, reject all, or walk through item-by-item.
7. **On approval:**
   - Update the YAML with the new chart state.
   - For each People note marked `update`, edit the relevant frontmatter fields (`role`, `manager`, `department`, `direct_reports`). **Never overwrite manually-maintained sections** (Profile, Working Style, Strengths, etc.).
   - For each `create`, write a new People note using `people-template.md` schema with YAML-derived defaults.
   - For each `mark departed`, flip `status: active` → `status: departed` and append a dated note in the Profile section.

## YAML schema

```yaml
# obsidian-people-seed-org-chart.yaml
# Source of truth for ChalkTalk People notes.
# Edit by hand from the most recent pinned org chart.

last_refreshed: 2026-05-08
chart_source: <description of the image — e.g. "Notion org chart, screenshot 2026-05-07">

people:
  - real_name: Ciaran Hollywood
    display_name: Ciaran
    slack_handle: ciaran
    slack_user_id: U0XXXXXXXX
    canonical_email: ciaran@chalktalk.academy
    role: Staff Engineer
    department: Engineering
    sub_team: Platform
    manager: Eric Du
    direct_reports:
      - Sarah Chen
    timezone: America/New_York
    location: New York, NY
    joined: 2024-01-15
    on_org_chart: true
    status: active

  - real_name: Sarah Chen
    ...

open_questions:
  - "Is Alex Rivera still on staff or did they depart? Chart shows them grayed out — need to confirm with HR."
  - "Sub-team for Mateo Garcia: chart shows Platform, Slack title says Growth. Which is current?"
```

### Field rules

- `last_refreshed` — ISO date, updated every time the YAML is touched.
- `chart_source` — free-form description of the image used. Include the date of the screenshot.
- `people[]` — flat list. Each entry maps to one People note.
- `manager` — string (the manager's `real_name`), not a wikilink. The wikilink form is reserved for the People note frontmatter.
- `direct_reports` — list of strings (each a `real_name`). Mirror of the `manager` field — both directions are stored for diffing.
- `on_org_chart: true` for everyone in the chart. Off-chart people (advisors, contractors, ex-employees Mo still tracks) are NOT in this YAML — they're maintained in their People notes only with `on_org_chart: false`.
- `status: active | on_leave | departed`.

## `open_questions` block

A free-form list at the bottom of the YAML for ambiguities that need human resolution. Examples:

- Names whose role is unclear from the chart.
- People whose status (active vs on-leave vs departed) couldn't be determined from the image.
- Sub-team conflicts between chart and Slack title.

Mo resolves these manually between refresh cycles. The agent should surface unresolved questions during refresh as a separate section in the confirmation summary:

```
OPEN QUESTIONS (carrying forward, 2):
1. Is Alex Rivera still on staff?
2. Sub-team for Mateo Garcia — Platform or Growth?
```

## What this YAML is NOT

- Not a CRM. Off-chart contacts (vendors, advisors, board members) belong in People notes with `on_org_chart: false`, not here.
- Not a Slack workspace export. Don't try to repopulate it from Slack — Slack lacks reporting structure.
- Not a permission system. The skill's writes to People notes don't gate on YAML presence.

## Cross-references

- People note schema and frontmatter rules → `people-template.md`
- New-person flag extraction (uses YAML to resolve aliases) → `extraction-rules.md`
