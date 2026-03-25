# marbaji-claude

Personal Claude Code skills marketplace.

## Skills

### /obsidian-memory
Project-first session memory using Obsidian. At session start, loads project context and current focus. During sessions, proactively saves after milestones. At session end, updates project docs and writes session logs. Presents a summary with categories for approval before writing.

### /technical-handoff-writer
Structures exploratory technical work (SQL, data analysis, algorithm validation) into an engineering handoff. Outputs two files: a curated handoff document and a companion development timeline (via claude-mem's `timeline-report`). Requires [claude-mem](https://github.com/thedotmack/claude-mem) for timeline generation.

### /inventory-checker
Displays a complete inventory of all installed Claude Code components — MCP servers (local and cloud, with status), plugin marketplaces, available skills (grouped by marketplace), npm/Python/Homebrew packages, and CLI tools.

## How obsidian-memory Fits Into the Memory Architecture

This skill is one layer of a three-layer memory system for Claude Code. Each layer solves a distinct problem:

### 1. Claude's Native Memory Ecosystem

Claude Code ships with built-in memory: **MEMORY.md** (auto-loaded facts about you and your projects), **Auto Memory** (Claude's daytime brain — takes notes as it works, but after 20+ sessions the notes become a mess of contradictions and stale entries), and **Auto Dream** (Claude's REM sleep — runs in the background at the start of your next session after 24h + 5 sessions, consolidating and pruning Auto Memory so it stays clean).

This gives Claude lightweight session-to-session continuity with zero effort. But it's a black box — you can't browse it outside Claude, there are no session logs, no deep search across past sessions, and no way to generate a project history report for someone else.

### 2. obsidian-memory (This Skill)

Writes to an Obsidian vault — a local folder of markdown files you can open and browse anytime. Maintains curated project docs, session logs with wikilinks, and a current-focus dashboard.

**Why it exists:** Removes the black box. You can verify what Claude knows, trace decisions to specific conversations, and see project status without starting a session. Also the best context source for Claude itself — ~50 lines per project vs thousands of raw observations.

### 3. claude-mem (Separate Plugin)

Runs a worker service that automatically captures every tool call as an observation in a SQLite database via PostToolUse hooks. Provides `mem-search` for deep cross-session recall and `timeline-report` for generating comprehensive project history deliverables.

**Why it exists:** (1) Safety net — if obsidian-memory's save is skipped (crash, timeout, closed tab), claude-mem captured everything via hooks. (2) Some use cases require granular, queryable history rather than obsidian's curated summaries. (3) Timeline reports pair with `/technical-handoff-writer` to produce development history deliverables for handoffs between teams.

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

## Install

```bash
claude plugin marketplace add marbaji-claude --source github --repo marbaji/marbaji-claude
claude plugin enable marbaji-claude@marbaji-claude
```

### Recommended: Install claude-mem

[claude-mem](https://github.com/thedotmack/claude-mem) is a separate plugin that provides automatic observation capture, cross-session search, and timeline reports. It's recommended for two reasons:

1. **Memory architecture** — claude-mem is the safety net and deep-recall layer in the three-layer memory system described above. obsidian-memory handles curated saves; claude-mem catches everything else automatically via hooks.
2. **technical-handoff-writer** — The `/technical-handoff-writer` skill generates a companion timeline report using claude-mem's `timeline-report`. Without claude-mem installed, only the handoff document is produced.

```bash
claude plugin marketplace add thedotmack/claude-mem
claude plugin enable claude-mem@claude-mem
```
