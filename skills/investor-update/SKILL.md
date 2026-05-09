---
name: investor-update
description: Generates a ChalkTalk investor update draft. Same source data as board-update but more narrative, less granular. Modeled on Q2 2026 investor decks. Use when Mo says "draft an investor update" or "/investor-update".
---

# Investor Update Draft Generator

Generates a narrative investor update from the Obsidian vault. Same source data as `board-update` but the composition is story-led, not minutiae-led — investors want the arc, not the changelog.

---

## Setup — Resolve vault path

Read the vault name from `~/.claude/obsidian-vault-name`. Resolve the absolute path:

```bash
echo "$HOME/Documents/$(cat ~/.claude/obsidian-vault-name)"
```

Use that absolute path for every Write tool call. Write tool does not expand `~`.

---

## Inputs

- `--since YYYY-MM-DD` (required)
- `--through YYYY-MM-DD` (optional, defaults to today)
- "since last investor update" — infer from the latest file in `Work/Chalktalk/Investor Updates/`. If empty, ask.

Confirm window back to Mo before working.

---

## Phase 1 — Gather

Same sources as `board-update` (read its Phase 1 if needed), plus one investor-specific addition:

1. **Shipping Log** — `Work/Chalktalk/Shipping Log.md`, scoped to window.
2. **Decisions** — `Work/Chalktalk/Decisions/*.md` in window.
3. **Projects** — `Work/Chalktalk/Projects/*.md` with mtime in window.
4. **Active priorities** — `Context/current-focus.md`.
5. **Style reference** — most recent file in `Work/Chalktalk/Investor Updates/`.
6. **Brag Doc** — `Personal/Brag Doc.md` (full file). This skill is allowed to draw heavier from founder-narrative content than `board-update`. Use Brag Doc entries to inform the "story of the period" framing and the "Wins" section.

---

## Phase 2 — Compose

Default structure (override only if the latest existing investor update uses a different one):

- **Story of the period** — 2 to 4 short paragraphs. What was the arc? What were we trying to prove? What did we learn? Pull tone from Brag Doc.
- **Headline metrics** — a small table or tight bullet list: ARR, customers, pipeline, runway, etc. If a number isn't in the vault, mark `[Mo to fill]`.
- **Wins** — 3 to 6 concrete wins. Cite vault evidence as wikilinks where possible.
- **Asks** — specific, addressable. Investors want to help; tell them how.

Composition guidance:

- Lead with story, not bullets. Investors compare narratives across companies; bullets bury the lede.
- Headline metrics belong in one tight block, not sprinkled.
- The Wins section should feel like Brag Doc material rephrased for an external audience.
- Skip granular product changelog detail. That's the board memo's job.

### Voice constraints (hard rules)

- **No em-dashes.** Per Mo's memory `feedback_no-em-dashes.md`.
- **No `>` blockquote indentation.** Breaks paste into Notion / email.
- Match the warmth and confidence of prior investor updates if a style reference exists.

---

## Phase 3 — Write and report

File path:

```
<vault>/Work/Chalktalk/Investor Updates/<through-date>-<slug>.md
```

Slug: a 1 to 3 word handle (e.g. `q2-2026`, `mid-april`). Ask Mo if ambiguous.

If the target file exists, prompt before overwriting.

Report back:

- Absolute path of the draft
- Section skeleton used (and source)
- Any `[Mo to fill]` placeholders
- Number of Brag Doc entries pulled in

Do not auto-send or publish.

---

## Notes / cross-references

- `board-update` and `investor-update` share Phase 1 logic; if you're building tooling, factor that out. The differences are entirely in Phase 2.
- The `quarterly-review` skill produces broader synthesis and can feed the next investor update — run it first when both are needed.
- Vault layout conventions: see the `obsidian-memory` skill.
