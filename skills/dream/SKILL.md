---
name: dream
description: Use to consolidate durable memory — merges duplicate principles, fixes stale dates, deletes contradicted facts, and tightens wording. Since 2026-08-05 the target is `~/.claude/work-principles.md` (the always-loaded curated file), not the per-project auto-memory directories, which are frozen and swept empty each session-end. Run after long sessions or any time you notice a principle referencing something outdated. Triggers on "dream", "/dream", "consolidate memory", "clean up memory", or "organize memories".
---

# Dream — Memory Consolidation

You are performing a dream — a reflective consolidation pass over durable memory. Synthesize what
you've learned recently into well-organized principles so future sessions orient quickly.

> **Target changed 2026-08-05.** The per-project auto-memory directories are **frozen** and swept
> empty at every session-end (see `obsidian-memory/references/session-end.md` Steps 3a.1 and 3a.2),
> and each `MEMORY.md` is now a stub explaining where things went. So there is nothing to consolidate
> there. **The target is `~/.claude/work-principles.md`** — the curated file imported by
> `~/.claude/CLAUDE.md`, which loads in every project.
>
> The job is unchanged and the failure mode is identical: merge bullets that say the same thing in
> different words, delete principles the codebase or a later decision has contradicted, verify any
> principle that names a file path, function or flag still refers to something real, and tighten
> anything that opens with an incident instead of its rule. Approval-gating matters MORE here than it
> did across scattered files: this is one file that every project loads, so a bad pass degrades every
> session rather than one project's.
>
> If a memory directory is NOT empty when you run, that is a signal the session-end sweep did not
> happen — report it rather than consolidating in place.

## Setup — Resolve paths

Determine the memory directory and transcripts directory for the current Claude Code session:

- **Memory directory:** the path mentioned in your system prompt's "auto memory" section. Claude Code uses `~/.claude/projects/<encoded-cwd>/memory/` per project. If your system prompt names a specific path, use that. If the user passes an explicit path argument (e.g., `/dream /some/other/memory/dir`), use that instead.
- **Index file:** `MEMORY.md` inside the memory directory.
- **Index size budget:** under 200 lines AND under ~25 KB.
- **Transcripts directory:** the parent of the memory directory (`~/.claude/projects/<encoded-cwd>/`). JSONL files there are session transcripts. They are LARGE — only grep narrowly, never read whole files.

## Phase 1 — Orient

- `ls` the memory directory to see what already exists
- Read `MEMORY.md` to understand the current index
- Skim each topic file mentioned in the index so you improve them rather than creating duplicates
- If `logs/` or `sessions/` subdirectories exist (assistant-mode layout), review recent entries there

## Phase 2 — Gather recent signal

Look for new information worth persisting and flag drifted facts. Sources in rough priority order:

1. **Existing memories that drifted** — facts that contradict the current state of the codebase, the current date, or other memory files. For any memory that names a file path, function, flag, or commit SHA, verify it still exists. A memory is a claim about what was true *when it was written* — it may be stale now.
2. **Cross-memory contradictions** — if two files disagree (e.g., one says "use X", another says "switched to Y"), note which one is current.
3. **Daily logs or session summaries** if `logs/` or `sessions/` subdirectories exist.
4. **Transcript search** — only if you need specific context to resolve an ambiguity. Use narrow grep:
   ```
   grep -rn "<narrow term>" ~/.claude/projects/<encoded-cwd>/ --include="*.jsonl" | tail -50
   ```
   Never read whole transcript files — they are huge.

Don't exhaustively read transcripts. Look only for things you already suspect matter.

## Phase 3 — Plan changes (do NOT write yet)

Before touching any file, build a proposed-changes table and present it to the user for approval. The table should have columns:

| # | Action | File | Reason |
|---|---|---|---|
| 1 | merge | feedback_a.md + feedback_b.md → feedback_a.md | Both cover the same rule with slightly different wording |
| 2 | update | project_x.md | Date "next Friday" → "2026-04-11" |
| 3 | delete | project_y.md | Workstream completed 2026-03-15, captured in git history |
| 4 | demote | MEMORY.md line for project_z | Index entry is 240 chars, content belongs in topic file |
| 5 | add | feedback_new.md | Recent rule from session not yet captured |

For each row, show the EXACT text that would change. Wait for the user to confirm (or pick which rows to apply) before doing any writes.

**Why approval gating:** memory files are durable on purpose. A wrong "dream" pass can erase real institutional knowledge. The cost of one round of confirmation is much lower than the cost of silently deleting a memory that mattered.

## Phase 4 — Apply approved changes

Once the user approves, apply the changes:

- **Merging:** combine content into one file, delete the other, update `MEMORY.md` to point at the survivor only
- **Updating:** rewrite the changed lines in place. Convert relative dates ("yesterday", "last week", "next Friday") to absolute dates in `YYYY-MM-DD` format
- **Deleting:** remove the file AND its index line
- **Demoting:** shorten the `MEMORY.md` entry to under ~150 chars and move the detail into the topic file
- **Adding:** create the new file with proper YAML frontmatter (`name`, `description`, `type`) per the auto-memory rules in your system prompt, then add an index pointer

The file format and type conventions (`user` / `feedback` / `project` / `reference`) live in your system prompt's auto-memory section — that is the source of truth. Don't invent new types.

## Phase 5 — Re-index

After all approved changes are applied:

- Verify `MEMORY.md` is under 200 lines AND under ~25 KB
- Verify each entry is `- [Title](file.md) — one-line hook` format under ~150 chars
- Verify every entry points to a file that exists
- Verify every memory file has an entry in `MEMORY.md`

## Output

Return a final summary with:

- **Files merged:** count + brief list
- **Facts updated:** count + brief list
- **Stale entries removed:** count + brief list
- **New entries added:** count + brief list
- **Index size:** lines and KB before / after
- **Files now in memory dir:** count

If memories were already tight and nothing needed cleanup, say so and exit cleanly without writing anything.

## Source

Built on the Piebald-AI Dream prompt (`agent-prompt-dream-memory-consolidation.md`, `ccVersion: 2.1.83`) at https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/agent-prompt-dream-memory-consolidation.md. The Phase 3 approval gate is added by this skill — the upstream prompt writes directly without confirmation, but that's risky for durable memory. Auto-Dream (the scheduled background variant) is gated behind a Claude Code feature flag and not yet generally available; this manual `/dream` skill is the equivalent until then.
