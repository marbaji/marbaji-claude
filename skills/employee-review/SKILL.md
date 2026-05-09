---
name: employee-review
description: Role-agnostic employee review draft generator. Single person or bulk. Uses Notion scorecard (mirrored locally as Competency notes) + ChalkTalk Values + vault evidence. Use when Mo says "draft a review for <name>" or "/employee-review".
---

# Employee Review Draft Generator

Generates evidence-backed review drafts using ChalkTalk's scorecard framework + Values, sourced from the Obsidian vault. Single-person or bulk. Bulk dispatches parallel subagents — surface the cost trade-off to Mo before kicking off.

---

## Setup — Resolve vault path

Read vault name from `~/.claude/obsidian-vault-name`. Resolve absolute:

```bash
echo "$HOME/Documents/$(cat ~/.claude/obsidian-vault-name)"
```

Write tool requires absolute paths.

---

## Inputs (mutually exclusive)

- `<name>` — single-person review (e.g. `/employee-review Sarah Chen`)
- `--reports-of <manager-name>` — every direct report of that manager
- `--all` — every person with a People note

Plus one shared input:

- `--period YYYY-Q[1-4]` (required) — derives the date window. Same mapping as `quarterly-review`.

Confirm the resolved scope and window back to Mo before any work.

---

## Cost trade-off (BULK only)

If `--reports-of` or `--all` is used, before dispatching subagents:

1. Count the resolved set (N people).
2. Tell Mo: "I'm about to dispatch N subagents in parallel, each doing ~5 evidence walks (1:1s, Decisions, Sessions grep, GitHub PRs, optionally Slack). Each subagent's response gets re-read every turn via the conversation history (per Mo's memory `feedback_subagent-driven-cost-check.md`)."
3. Offer three options:
   - **Conversation-history mode (default)** — subagents return full reports inline. High recurring token cost but easiest to iterate.
   - **Silent-writer mode** — subagents write directly to vault files and return only file paths + a 1-line summary. Lowest token cost. Iteration requires re-reading files.
   - **Hybrid** — subagents return summaries inline, write detail to vault. Medium cost.
4. Wait for Mo to pick.

Single-person path skips this gate.

---

## Phase 1 — Single-person path

Given `<name>`:

### 1.1 Resolve identity

Read the People note: search `Work/Chalktalk/People/` for a file matching the name. Pull `role`, `manager`, `github_handle`, `slack_handle`, and any team tags.

### 1.2 Resolve scorecard

- `Work/Chalktalk/Competencies/<dept>/*.md` filtered by `role:` frontmatter matching the person's role. These mirror the Notion scorecard.
- `Work/Chalktalk/Values.md` — the canonical ChalkTalk Values (cross-role).

### 1.3 Walk vault evidence (period-scoped)

- All `Work/Chalktalk/1-on-1s/<First Name> YYYY-MM-DD.md` files in window.
- All `Work/Chalktalk/Decisions/*.md` in window where the person is in `stakeholders:` or `owner:`.
- All `Sessions/*/*.md` in window where the person's name appears (use `grep -rli "<First Name>" <vault>/Sessions/<YYYY-MM>/`).
- If `github_handle` is set: pull their PRs in window across both orgs:
  ```bash
  gh api -X GET "search/issues" -f q="org:ChalkTalk org:marbaji author:<handle> type:pr created:<since>..<through>" --paginate
  ```
  Use the PR titles, merge status, and review comments — not the diffs.
- If their team includes Sales: scan their contributions in `#sales` channels via the Slack MCP. Use `mcp__slack__conversations_search_messages` with `from:<handle>` filter scoped to window. (Subagents must call `ToolSearch` to load Slack tool schemas before invoking — see `CLAUDE.md` MCP rules.)

### 1.4 Score

For each scorecard outcome and each competency, assign **1 to 5** using the ChalkTalk framework:

| Score | Meaning |
|---|---|
| 1 | Far below expectations |
| 2 | Below expectations |
| 3 | **Meeting expectations** (default for solid work) |
| 4 | Exceeding expectations |
| 5 | **Exceptional — reserved**, multiple standout instances |

Hard rules:

- **Every score must cite vault evidence as a wikilink in its justification.** No wikilinks → no score → write `Insufficient evidence — N/A`.
- Do not fabricate. If the only evidence is a single 1:1 mention, that's a 3 with a one-line justification, not a 4.
- 5 is rare. Triggering 5 requires multiple distinct evidence points showing standout impact.

### 1.5 Values

For each entry in `Work/Chalktalk/Values.md`, cite at least one concrete instance from the evidence walk. If none, mark `Insufficient evidence` for that value — do not invent.

### 1.6 Write

Output path:

```
<vault>/Work/Chalktalk/Reviews/<period>/<First Last>.md
```

Match the Notion scorecard table format:

| Competency | Self Score | Manager Score | Justification (with wikilink evidence) |

Self Score column is left blank — Mo and the report fill that during the conversation. Manager Score is what this skill assigns.

After the table, include:

- A Values section with cited instances per value
- A "Strengths to lean into" short narrative (3 to 5 bullets)
- A "Growth areas" short narrative (1 to 3 bullets)

### Voice constraints

- **No em-dashes** (`feedback_no-em-dashes.md`).
- **No `>` blockquote indentation** — Mo will paste this into Notion.

---

## Phase 1 — Bulk path

After the cost trade-off gate is resolved:

1. Resolve the person list (filter People notes by `manager:` for `--reports-of`, all for `--all`).
2. Dispatch one subagent per person, each running the full single-person path above. Subagents must:
   - Receive the resolved vault path explicitly
   - Receive instructions to call `ToolSearch` before any MCP tool (Slack, GitHub if applicable)
   - Be told their output mode (conversation-history vs silent-writer vs hybrid) per Mo's choice
3. Aggregate results into a master report at:
   ```
   <vault>/Work/Chalktalk/Reviews/<period>/_index.md
   ```
   Listing each person, their file path, and a 2 to 3 sentence summary.

---

## Phase 3 — Report

Return to Mo:

- Path(s) written
- For each review: a one-line headline (e.g. "3.4 average — strong on Customer Empathy, gap on Eng Velocity")
- Any `Insufficient evidence` flags
- Any wikilinks that resolved to missing files (means the People/Decisions/Competencies layout drifted)

Do not auto-send to anyone. Drafts only.

---

## Notes / cross-references

- `quarterly-review` produces the per-report rollup that feeds this skill — run it first if you want context before drafting reviews.
- Scorecard structure mirrors the Notion source of truth. If Competency notes drift from Notion, that's a vault hygiene problem, not a skill problem.
- Vault folder structure assumed by this skill is the same one defined in `obsidian-memory`. Update both if the vault layout changes.
