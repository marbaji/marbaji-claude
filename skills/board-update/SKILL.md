---
name: board-update
description: Generates a date-ranged ChalkTalk board update draft from the obsidian vault Shipping Log + Decisions + project changes. Modeled on the Oct 2025 ChalkTalk Board Memo style. Use when prepping for a board meeting or when Mo says "draft a board update for <period>" or "/board-update".
---

# Board Update Draft Generator

Generates a draft ChalkTalk board update by synthesizing the Obsidian vault's Shipping Log, Decisions, and active Projects across a date window. The output is a markdown file Mo can paste into Notion or email.

---

## Setup — Resolve vault path

Read the vault name from `~/.claude/obsidian-vault-name`. Resolve the absolute path:

```bash
echo "$HOME/Documents/$(cat ~/.claude/obsidian-vault-name)"
# e.g. /Users/mohannadarbaji/Documents/Claude Code Obsidian
```

Use that absolute path for every Write tool call this session. The Write tool does not expand `~` — see `obsidian-memory/references/installation-flow.md` (sister skill) if confused.

---

## Inputs

- `--since YYYY-MM-DD` (required) — start of the date window
- `--through YYYY-MM-DD` (optional, defaults to today) — end of the window
- "since last board meeting" — Mo may phrase it this way. Infer `--since` from the date prefix of the most recent file in `Work/Chalktalk/Board Updates/`. If that folder is empty, ask Mo for an explicit date.

Confirm the resolved window back to Mo before doing any work. Cost-free, prevents drafting against the wrong period.

---

## Phase 1 — Gather

Pull from these vault sources, scoped to the window:

1. **Shipping Log** — `Work/Chalktalk/Shipping Log.md`. Filter entries to the date window. Most entries are dated headings or bullets; grep for `YYYY-MM` matches in the window.
2. **Decisions** — every `Work/Chalktalk/Decisions/*.md` whose `date:` frontmatter (or filename date prefix) falls in the window.
3. **Projects** — every `Work/Chalktalk/Projects/*.md` whose file mtime falls in the window. Use `find` with `-newermt` and `! -newermt`:
   ```bash
   find "<vault>/Work/Chalktalk/Projects" -name "*.md" \
     -newermt "<since>" ! -newermt "<through-plus-1-day>"
   ```
4. **Active priorities** — `Context/current-focus.md` (full file).
5. **Style reference** — the most recent file in `Work/Chalktalk/Board Updates/` (if any). This anchors structure and tone.

If the style reference exists, parse its top-level section headings and use them as the skeleton for the new draft. If it does not exist, fall back to the default skeleton in Phase 2.

---

## Phase 2 — Compose

Match the section structure of the latest existing memo. If none exists, default to:

- **Headlines** — 3 to 5 bullets, the most important things to know
- **Financial / Runway** — pull from Mo's notes; if no recent number is in the window, write `[Mo to fill]` rather than fabricate
- **Product Updates** — synthesize from Shipping Log + Projects
- **GTM Updates** — sales / pipeline / customer wins (look in Decisions and Projects with `area: gtm` or similar tags)
- **Risks / Asks** — concrete, named risks; explicit asks for the board

Per-section rules:

- Each bullet should cite vault evidence as a wikilink, e.g. `[[Shipping Log#2026-04-22]]` or `[[Decisions/2026-04-15-pricing-tier]]`.
- Numbers must come from the vault. If a metric is mentioned but the source is unclear, write `[verify: <metric>]` instead of guessing.
- Keep bullets crisp. Board memos are scannable.

### Voice constraints (hard rules — Mo will paste this)

- **No em-dashes.** Use commas, semicolons, parens, or split into two sentences. Mo's memory `feedback_no-em-dashes.md` is the source of this rule.
- **No `>` blockquote indentation.** Mo copy-pastes into Notion, where blockquotes break formatting.
- No first-person plural ("we") unless the latest memo uses it consistently.

---

## Phase 3 — Write and report

Generate a slug from the window: e.g. `Q2-window` or `april-board` (ask Mo if ambiguous). File path:

```
<vault>/Work/Chalktalk/Board Updates/<through-date>-<slug>.md
```

If the file already exists, prompt Mo before overwriting.

Write the draft, then return to Mo:

- Absolute path of the new file
- The section skeleton used (and whether it came from a prior memo or the default)
- Any `[Mo to fill]` or `[verify: ...]` placeholders left in the draft

Do not auto-publish, post, or sync anywhere. The draft is for Mo to review.

---

## Notes / cross-references

- Shares vault layout conventions with the `obsidian-memory` skill — see its README for the canonical folder structure.
- The investor-update skill uses the same source data with a more narrative composition phase.
- The quarterly-review skill operates on a wider window and includes brag-doc + competency rollups; do not duplicate its work here.
