# marbaji-claude

Personal Claude Code skills marketplace.

## Install

```bash
claude plugin marketplace add marbaji-claude --source github --repo marbaji/marbaji-claude
claude plugin enable marbaji-claude@marbaji-claude

claude plugin marketplace add thedotmack/claude-mem
claude plugin enable claude-mem@claude-mem
```

## Skills

### /obsidian-memory
Project-first session memory using Obsidian. At session start, loads project context, current focus, and runs periodic vault health checks (lint). During sessions, proactively saves after milestones and logs URLs to a Sources/ citation trail. At session end, updates project docs, writes session logs, and runs an extraction pass that promotes decisions, shipping events, and brag-worthy moments into their own structured files. Presents a summary with categories for approval before writing.

The skill ships generic primitives: vault layout, templates (People, Competency, Decision, 1:1), extraction rules, and four invokable companion skills below. Adopters populate their own private vault content (org chart, People notes, scorecards, Values, Shipping Log, Brag Doc) — see `skills/obsidian-memory/references/adopting-this-skill.md`.

**Recommended setup after enabling the plugin** (both are token-cost wins; skill falls back gracefully if skipped):
- **SessionStart hook** at `skills/obsidian-memory/scripts/session-start-context.sh` — injects vault context procedurally instead of via LLM file reads (~3-4x token reduction at session start). Wire-up in `references/session-start-hook.md`.
- **QMD semantic search MCP** — adds `mcp__qmd__query` for chunked semantic recall over the vault. Falls back to `obsidian search:context` if not installed. Setup in `references/qmd-setup.md`. Note: QMD is read/search only; vault writes still go through `obsidian` CLI + Write tool unchanged.

### /board-update
Generates a date-ranged board update draft from the Obsidian vault's Shipping Log + Decisions + project changes. Modeled on the user's most recent existing board memo style. Use when prepping for a board meeting.

### /investor-update
Generates an investor update draft from the same vault sources. Use when prepping for a monthly investor email or KPI digest.

### /quarterly-review
Synthesizes a personal quarterly review across sessions, brag entries, decisions, and shipping events. Output goes to `Personal/Quarterly Reviews/YYYY-Q[1-4].md`.

### /employee-review
Drafts an employee review by walking backlinks from the target person's Competency evidence in session logs, 1:1 notes, and Decisions. Role-agnostic. Single or bulk variants.

### /technical-handoff-writer
Structures exploratory technical work (SQL, data analysis, algorithm validation) into an engineering handoff. Outputs two files: a curated handoff document and a companion development timeline (via claude-mem's `timeline-report`). Requires [claude-mem](https://github.com/thedotmack/claude-mem) for timeline generation.

### /inventory-checker
Displays a complete inventory of all installed Claude Code components — MCP servers (local and cloud, with status), plugin marketplaces, available skills (grouped by marketplace), npm/Python/Homebrew packages, and CLI tools.

### /instagram-transcribe
Transcribes Instagram Reels (or any yt-dlp-supported URL) using yt-dlp and Whisper locally. Downloads audio, transcribes, generates a summary, and saves to a descriptive folder.

### /skill-inventory-checker
Compares all skills across GitHub repos (`ChalkTalk/claude`, `marbaji/marbaji-claude`), Desktop folders, and `~/.claude/skills/`. Detects broken symlinks, missing skills, standalone copies that should be symlinks, and untracked skills. Offers concrete fix commands.

## Hooks

> **Canonical source:** Hooks are now maintained in [ChalkTalk/claude](https://github.com/ChalkTalk/claude) at `skills/references/hooks/`. The copies in this repo's `hooks/` directory are historical — the `chalktalk-setup` skill installs from the ChalkTalk repo.

## Three-Layer Memory Architecture: How `/obsidian-memory`, `claude-mem`, and Claude's Native Memory Create Persistent Context Across Sessions

This skill is one layer of a three-layer memory system for Claude Code. Each layer solves a distinct problem:

### 1. Claude's Native Memory Ecosystem

Claude Code ships with built-in memory: **MEMORY.md** (auto-loaded facts about you and your projects), **Auto Memory** (Claude's daytime brain — takes notes as it works, but after 20+ sessions the notes become a mess of contradictions and stale entries), and **Auto Dream** (Claude's REM sleep — runs in the background at the start of your next session after 24h + 5 sessions, consolidating and pruning Auto Memory so it stays clean).

This gives Claude lightweight session-to-session continuity with zero effort. But it's a black box — you can't browse it outside Claude, there are no session logs, no deep search across past sessions, and no way to generate a project history report for someone else.

> **Update 2026-08-05 — this layer is now a staging area, not a store.** Auto Memory is scoped per *working directory*, not per project, so the same lesson learned in two directories produced two copies that could not see each other. An audit found **148 files across 7 silos**, one index at 124 lines (~3.4k tokens loaded every session), and the two largest silos duplicating each other by concept with zero filename overlap.
>
> Auto Memory still captures corrections at the moment they happen — that part is right. What changed is where they *end up*:
>
> | lesson shape | home | loads |
> |---|---|---|
> | Cross-project principle or procedure | `~/.claude/work-principles.md`, imported by `~/.claude/CLAUDE.md` via a one-line `@` stub | every session, every project |
> | Repo standard scoped to a path glob | that repo's `.claude/rules/<area>.md` | when editing matching paths, and PR-reviewed so it cannot rot silently |
> | Skill-specific trap | that skill's gotchas file | when the skill runs |
> | Write-up, tool recipe, project fact | the Obsidian vault | on search |
> | Personal, non-shareable, one repo | that repo's `CLAUDE.local.md` | in that repo |
>
> The session-end ritual sweeps the memory directory each close, re-homes what the harness staged, and deletes the file — so **a non-empty memory directory is unfinished work, not a store**. A directory accretes by construction; a curated file can only be edited, which is what makes the growth stop. See `skills/obsidian-memory/references/session-end.md` Steps 3a.1 and 3a.2.

### 2. obsidian-memory (This Skill)

Writes to an Obsidian vault — a local folder of markdown files you can open and browse anytime. Maintains curated project docs, session logs with wikilinks, and a current-focus dashboard.

**Why it exists:** Removes the black box. You can verify what Claude knows, trace decisions to specific conversations, and see project status without starting a session. Also the best context source for Claude itself — ~50 lines per project vs thousands of raw observations.

#### Source Logging & Citation Trail

Every URL shared in conversation gets logged to a `Sources/` folder — one markdown file per URL with Summary (objective description), Takeaways (personal learnings), and bidirectional wikilinks to the session where it was discussed. This is the raw citation layer.

On top of that, curated **aggregated project pages** (e.g., `Work/Chalktalk/Knowledge/skill-architecture-sources.md`) roll up relevant sources with analysis for specific projects. You read the aggregated pages; the Sources/ folder is the searchable citation trail feeding them. Inspired by [Karpathy's raw/ → wiki/ pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

#### Vault Health Checks (Lint)

Built into the session-start ritual. Every 7 days, obsidian-memory automatically scans for:
- **Abandoned projects** — active in current-focus but untouched for 14+ days (with day count). Framed positively: abandoning low-priority projects is good prioritization.
- **Broken wikilinks** — current-focus references a project doc that doesn't exist
- **Status drift** — project doc says `active` but current-focus lists it as complete (or vice versa)
- **Orphan project docs** — files not referenced from current-focus
- **Stale Next Steps** — unchanged across 3+ sessions
- **Empty sections** — project docs with blank Overview, Key Findings, or Next Steps

Produces a report — does not modify project docs. You glance at it and decide what to do.

### 3. claude-mem (Separate Plugin)

Runs a worker service that automatically captures every tool call as an observation in a SQLite database via PostToolUse hooks. Provides `mem-search` for deep cross-session recall and `timeline-report` for generating comprehensive project history deliverables.

**Why it exists:** Incredibly more thorough. You don't need this extreme level of detail in your Obsidian file. But some use cases require granular, queryable history rather than Obsidian's curated summaries. For example, `/technical-handoff-writer` is designed to produce development history deliverables for handoffs between teams. It doesn't tap into Obsidian only — it taps into claude-mem for a token-intensive query to create an entire archaeological narrative summary with details of what happened across sessions.

### How They Work Together

```
┌─────────────────────────────────────────────────────┐
│                  SESSION START                       │
│                                                     │
│  Claude Native Memory ─── loads automatically       │
│    (MEMORY.md + Auto Memory + Auto Dream)           │
│  claude-mem ($CMEM)    ─── loads automatically      │
│  obsidian-memory       ─── loads via skill          │
│                                                     │
│  Total: ~3K tokens / 0.3% of 1M context window     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                DURING SESSION                       │
│                                                     │
│  claude-mem ─── silently captures every tool call   │
│                 (PostToolUse hook, zero effort)      │
│                                                     │
│  obsidian-memory ─── proactively saves after        │
│                      milestones (Claude-initiated)  │
│                                                     │
│  Auto Memory ─── saves when patterns noticed        │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│             WHEN DEEPER CONTEXT NEEDED              │
│                                                     │
│  1st: Obsidian project doc (curated, ~50 lines,    │
│       best signal-to-noise ratio)                   │
│                                                     │
│  2nd: claude-mem mem-search (granular, raw,         │
│       cross-session detail)                         │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  SESSION END                        │
│                                                     │
│  obsidian-memory ─── final save + verify files      │
│                      (user triggers before exit)    │
│                                                     │
│  claude-mem ─── auto session-complete (hook)        │
│                                                     │
│  Auto Dream ─── consolidates Auto Memory in the     │
│    background at start of next session (triggers    │
│    after 24h + 5 sessions since last consolidation) │
└─────────────────────────────────────────────────────┘
```

**obsidian-memory** = daily driver (context, visibility, trust)
**claude-mem** = safety net + power tool (capture, recall, deliverables)
**Claude Native Memory** = foundation (lightweight continuity, self-maintaining)
