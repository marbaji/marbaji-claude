# obsidian-memory skill

Persistent memory and context management for Claude Code via an Obsidian vault. At session start the skill loads project context, current focus, and recent session history so Claude arrives oriented — without burning tokens re-reading dozens of files. At session end it runs an extraction pass that promotes decisions, shipping events, and brag-worthy moments into their own structured files, updates project docs, and writes a dated session log. The session-end ritual is implemented by a Python CLI helper (`helpers/session_end.py`) that accepts a YAML manifest from the agent, validates it with Pydantic, runs preflight checks, and atomically writes up to 12 vault artifacts. The skill operates invisibly in the background; the user only sees the session-end approval summary before any writes happen.

---

## When it activates

- **Session start** — fires on every new Claude Code conversation. If the optional SessionStart hook is wired up (`scripts/session-start-context.sh`), vault context is injected procedurally before the LLM sees any prompt (~3-4x cheaper). Otherwise the agent reads SKILL.md and executes `references/session-start.md` manually.
- **Session end** — fires when the user says "done", "exit", "that's all", "wrap up", or similar. Agent reads `references/session-end.md`, assembles a YAML manifest, and calls `helpers/session_end.py`.
- **Recall requests** — fires when the user asks "what did we do about X" or similar. Agent searches the vault using `mcp__qmd__query` (or falls back to `obsidian search:context`) rather than reading whole files.
- **Throughout the session** — proactively saves after milestones, captures URLs as Source files, and tags competency evidence in session logs.

---

## What it produces

| Artifact | Location in vault |
|---|---|
| Session log | `Sessions/YYYY-MM/YYYY-MM-DD-<topic>.md` |
| Decision files | `Work/<Org>/Decisions/YYYY-MM-DD-<slug>.md` |
| Shipping Log bullets | `Work/<Org>/Shipping Log.md` (prepended under `## YYYY-MM` heading) |
| Brag Doc bullets | `Personal/Brag Doc.md` (prepended under `## YYYY Q<N>` heading) |
| Project doc updates | `Work/<Org>/Projects/<slug>.md` (section appended) |
| New project docs | `Work/<Org>/Projects/<slug>.md` (new file) |
| `current-focus.md` edits | `Context/current-focus.md` (upsert, remove, move-to-complete) |
| Source citation files | `Sources/YYYY-MM-DD-<name>.md` |
| People note flags | Stdout only — operator creates the note manually |
| Correction-taxonomy ledger updates (opt-in) | `Personal/Projects/agentic-loops/taxonomy-evidence-ledger.md` |
| Archived session transcripts (opt-in; only when a session mints/promotes a taxonomy category) | `Personal/Projects/agentic-loops/transcripts/` |

---

## The feedback loops

The artifact table above says *what* gets written; this is *why*. Session-end isn't just a save — it runs four loops that compound across sessions:

- **Extraction loop.** Decisions, shipping events, and brag-worthy moments get promoted out of the chronological session log into their own indexable files, after one batched approval. Six months later you find the decision by searching Decisions/, not by re-reading session logs.
- **Staleness sweep.** Any active project untouched for 14 days (backlog: 30) surfaces a retire / complete / snooze question at close. Code-enforced — the helper refuses to write if a due project goes unaddressed — so the Active list stays honest instead of only ever growing.
- **Learning routing.** A lesson that lives only in a session log is a lesson the next session repeats — nothing loads it in time. At close, each lesson is routed to a home future sessions actually read: auto-memory (cross-session habits), repo rules (path-scoped standards, opened as a PR before the session ends), or a skill's gotchas file (task-scoped). The session log keeps the story; the home keeps the enforcement.
- **Correction-taxonomy loop (opt-in).** Sweeps the moments you *corrected the agent* into a private evidence ledger in your vault. First occurrence of a pattern parks as an unverified draft; the second occurrence triggers a one-click promotion prompt; a promoted rule is routed via the learning-routing loop above, while the ledger keeps counts + citations as the audit trail. Sessions that mint or promote a category get their transcript archived permanently (Claude Code deletes transcripts after months; the archive is the durable receipt). Activates only if the ledger file exists — create it via `references/adopting-this-skill.md` § "Optional: correction-taxonomy evidence ledger"; otherwise the step is skipped.

---

## File map

### `SKILL.md`

The agent manifest — read at skill activation. Defines the operations map, retrieval rules, vault path resolution, and the session-start/end trigger conditions. Start here to understand how the skill runs.

---

### `helpers/`

Python helpers invoked by the agent via CLI.

- **`helpers/session_end.py`** — Vault write engine for the session-end phase. Accepts a YAML manifest, validates it against a Pydantic v2 schema, runs preflight checks against the live vault, then writes session log and extracted artifacts atomically. All-or-nothing on preflight failure — no partial writes. CLI: `python3 session_end.py --manifest <path> [--dry-run] [--vault-path <path>] [--only <sections>]`. Full schema and worked examples: [`references/session-end-helper.md`](references/session-end-helper.md).

- **`helpers/tests/`** — pytest suite for `session_end.py`. Includes `conftest.py`, `test_session_end.py`, and a `fixtures/` folder with sample manifests (`manifest_full.yaml`, `manifest_minimal.yaml`) and a minimal vault tree used by integration tests.

---

### `references/`

On-demand reference docs — the agent loads only the one it needs for the current operation.

| File | What it covers |
|---|---|
| `session-end-helper.md` | Full CLI reference, Pydantic schema for every manifest field, exit codes, and three worked examples for `session_end.py` |
| `session-start.md` | Step-by-step session-start ritual (context loading, weekly lint trigger) |
| `session-end.md` | Step-by-step session-end ritual (project identification, staleness sweep, extraction approval, learning routing, opt-in correction-taxonomy sweep, manifest assembly) |
| `session-start-hook.md` | How to wire up the SessionStart hook for the ~3-4x token reduction at session start |
| `installation-flow.md` | First-time setup wizard (vault path, org name, hook installation, vault scaffolding) |
| `qmd-setup.md` | How to install and register the QMD semantic search MCP for chunked vault recall |
| `core-operations.md` | How to search past work, create project docs, capture quick notes, and update context |
| `extraction-rules.md` | Trigger conditions and destination paths for decisions, shipping-log entries, brag entries, and new-person flags |
| `file-operations.md` | Decision tree for which write tool to use (obsidian CLI vs Write tool vs append vs frontmatter property) |
| `vault-structure.md` | Full vault folder layout with descriptions of every top-level directory |
| `project-doc-rules.md` | Status field values and rules for what gets replaced vs prepended in project docs |
| `vault-lint-rules.md` | 7-day health check rules (abandoned projects, broken wikilinks, status drift, orphan docs, stale next steps) |
| `source-logging-rules.md` | How to capture URLs as Source files and derive session-log bullets from them |
| `competency-tagging.md` | When and how to tag competency evidence in session logs with wikilinks so `employee-review` can walk backlinks |
| `guidelines.md` | Always-do vs ask-first behavioral rules for vault writes |
| `conventions.md` | File naming, tag vocabulary, troubleshooting tips, and skill-integration notes |
| `adopting-this-skill.md` | How to populate your own vault with org-specific data (org chart, People notes, Values, etc.) + how to opt in to the correction-taxonomy evidence ledger |
| `gotchas.md` | Failure modes accumulated from real runs — read before using the skill |
| `people-template.md` | Schema and section layout for `Work/<Org>/People/<Name>.md` |
| `competency-template.md` | Schema and section layout for `Work/<Org>/Competencies/<Competency>.md` |
| `decision-template.md` | Schema and section layout for `Work/<Org>/Decisions/YYYY-MM-DD-<slug>.md` |
| `one-on-one-template.md` | Schema and section layout for `Work/<Org>/1-on-1s/<First Name> YYYY-MM-DD.md` |
| `org-chart-source.md` | Location and format of the hand-maintained org-chart YAML used to seed People notes |
| `future-1on1-import.md` | Forward-looking spec for automated 1:1 import from Zoom/Oliv (not yet implemented) |

---

### `scripts/`

- **`scripts/session-start-context.sh`** — SessionStart hook. Emits structured vault context (current focus, recent sessions, project listing, git activity) as a system-reminder block at session start. Procedural shell, not LLM tokens — targets ~2K tokens vs ~15-20K when the agent reads each file itself. Wire-up instructions in `references/session-start-hook.md`.

---

## Three-part memory system context

`obsidian-memory` is the long-form persistent layer of a three-part memory system. The other two layers are Claude's native memory (MEMORY.md + Auto Memory + Auto Dream) and `claude-mem` (SQLite observation capture via PostToolUse hooks). Vault files are readable outside Claude in any Obsidian client, giving you a verifiable and browsable record rather than a black box. For the full architecture diagram and how all three layers interact, see the [marbaji-claude top-level README](../../README.md).

---

## Configuration

First-time setup: run `/obsidian-memory` in a fresh session and follow the wizard in `references/installation-flow.md`. The skill reads two config files at session start:

- `~/.claude/obsidian-vault-path` — absolute filesystem path to the vault (set by the installer post-2026-05; preferred)
- `~/.claude/obsidian-org-name` — your org folder name under `Work/` (defaults to `Chalktalk` if absent)

Legacy installs may have `~/.claude/obsidian-vault-name` instead; the skill falls back to `~/Documents/<name>` in that case. The `session_end.py` helper resolves the same fallback chain.

Optional (recommended): install the QMD semantic search MCP for chunked vault recall. Setup: `references/qmd-setup.md`. Without it, the skill falls back to `obsidian search:context` (BM25 only).
