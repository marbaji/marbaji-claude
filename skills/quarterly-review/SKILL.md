---
name: quarterly-review
description: Cross-90-day vault synthesis — North Star alignment, brag doc auto-population, competency rollup per direct report, recurring patterns. Use at end of each quarter or when Mo says "/quarterly-review" or "do my quarterly review".
---

# Quarterly Review — 90-Day Vault Synthesis

Synthesizes 90 days of Obsidian vault activity into a quarterly review for Mo: North Star alignment, brag-doc gaps, competency rollups for each direct report, and cross-cutting patterns.

---

## Setup — Resolve vault path

Read the vault name from `~/.claude/obsidian-vault-name`. Resolve absolute:

```bash
echo "$HOME/Documents/$(cat ~/.claude/obsidian-vault-name)"
```

Write tool requires absolute paths.

---

## Inputs

- `--quarter YYYY-Q[1-4]` (required) — e.g. `2026-Q1`

Derive the date window from the quarter:

| Quarter | Window |
|---|---|
| Q1 | Jan 1 to Mar 31 |
| Q2 | Apr 1 to Jun 30 |
| Q3 | Jul 1 to Sep 30 |
| Q4 | Oct 1 to Dec 31 |

Confirm window back to Mo before proceeding.

---

## Phase 1 — Gather

Pull broadly across the vault for the quarter:

1. **All Session logs in range** — `Sessions/YYYY-MM/*.md` for the months covering the quarter.
2. **Current focus snapshot** — `Context/current-focus.md` (current state, not historical).
3. **1:1s** — `Work/Chalktalk/1-on-1s/*.md` whose filename date prefix is in the window.
4. **Decisions** — `Work/Chalktalk/Decisions/*.md` in window.
5. **Shipping Log** — `Work/Chalktalk/Shipping Log.md`, scoped to window.
6. **North Star** — search for the declared annual goal:
   - First check `Context/about-me.md`.
   - If not there, grep `Sessions/` for "North Star" or "annual goal" and use the most recent definitive mention.
   - If still not found, ask Mo to state it before continuing — alignment can't be scored against an unstated target.
7. **Brag Doc** — `Personal/Brag Doc.md` (full file).
8. **People notes** — `Work/Chalktalk/People/*.md` (or wherever People notes live in this vault). Identify direct reports via `manager: Mo Arbaji` in frontmatter.

---

## Phase 2 — Synthesize

Produce four synthesis blocks:

### 2a. North Star alignment

- What advanced toward the declared North Star? Cite specific Sessions / Decisions / Shipping Log entries as wikilinks.
- What didn't move? Be honest about stalls.
- What shifted? If priorities changed mid-quarter, note when and why (look for Decisions tagged `priority-shift` or sessions discussing re-scoping).

### 2b. Brag Doc gaps

- Scan sessions and shipping log for brag-worthy moments not yet in `Personal/Brag Doc.md`.
- Heuristics: "shipped", "launched", "closed", "saved", "unblocked", "hired", named recognition from team/customers.
- Propose 3 to 8 candidate entries in Brag Doc style (terse, first-person, dated).
- At Phase 3 time, offer to append them. Do not auto-append.

### 2c. Competency rollup per direct report

For each person where People note has `manager: Mo Arbaji`:

- Pull all 1:1 files in window with that person.
- Pull Decisions where they appear in `stakeholders` or `owner`.
- Cross-reference Competency notes — `Work/Chalktalk/Competencies/<dept>/*.md` filtered to their role.
- Produce a per-person block:
  - **Highlights** — key 1:1 moments and shipped work
  - **Demonstrated competencies** — link competency notes where evidence supports it
  - **Open growth areas** — competencies where the file lists expectations but the quarter has no evidence

Score nothing here — this is a rollup for Mo's reflection, not a review. Use the `employee-review` skill when actual reviews are due.

### 2d. Patterns

- Recurring blockers across the quarter
- Recurring wins
- Themes (e.g. a specific customer, a tech debt area, a hiring focus)

Rely on actual session/decision frequency, not vibes. Cite at least 3 sources per pattern claim.

---

## Phase 3 — Write and offer

Write the synthesis to:

```
<vault>/Personal/Quarterly Reviews/<quarter>.md
```

(e.g. `Personal/Quarterly Reviews/2026-Q1.md`)

If file exists, prompt before overwriting.

After writing, ask Mo:

1. "I found N candidate Brag Doc entries. Want me to append them to `Personal/Brag Doc.md`?" — show the candidates inline. Wait for confirmation per item or batch.
2. "Want me to draft `employee-review` runs for any of these N reports?" — offer the names.

### Voice constraints

- **No em-dashes.** `feedback_no-em-dashes.md`.
- **No `>` blockquote indentation** in any text Mo will paste elsewhere.

---

## Notes / cross-references

- `employee-review` is the natural follow-on for the per-report sections. This skill produces the rollup; that skill produces the formal review.
- `obsidian-memory` skill defines the vault folder structure this skill assumes.
- For investor / board narrative outputs covering the same quarter, run `investor-update` or `board-update` separately — they read different sections and use different voice.
