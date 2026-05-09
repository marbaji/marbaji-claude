---
name: obsidian-memory
description: Use at the start and end of every Claude Code session, and whenever you need to recall past work — loads and persists context via an Obsidian vault, saves session logs automatically, searches prior sessions, and maintains an evolving project knowledge graph.
---

# Obsidian Memory Management

Persistent memory and context management for Claude Code via an Obsidian vault.

> **Read `references/gotchas.md` before using this skill.** It lists the failure modes the skill has hit in real runs — non-existent CLI subcommands, vault-path confusion between `obsidian` CLI and the Write tool, and the session-end approval step that must never be skipped.

---

## Step 0 — Setup Detection (Always Run First)

Before doing anything else, check if this skill has been configured:

```bash
cat ~/.claude/obsidian-vault-path 2>/dev/null || cat ~/.claude/obsidian-vault-name 2>/dev/null
```

- **Either file exists** → read the vault path / name, use it throughout. Proceed.
- **Neither file exists** → read `references/installation-flow.md` and run the setup wizard before proceeding.

---

## Vault Location

Resolve the vault's full filesystem path once at session start. The skill stores configuration in two files; read whichever is available:

```bash
# Preferred: full path (set by the installer post-2026-05)
VAULT_PATH="$(cat ~/.claude/obsidian-vault-path 2>/dev/null)"
# Legacy fallback: name only, derived path under ~/Documents/
if [[ -z "$VAULT_PATH" ]]; then
  VAULT_NAME="$(cat ~/.claude/obsidian-vault-name 2>/dev/null)"
  [[ -n "$VAULT_NAME" ]] && VAULT_PATH="$HOME/Documents/$VAULT_NAME"
fi
VAULT_NAME="$(basename "$VAULT_PATH")"
echo "$VAULT_PATH"   # e.g. /Users/mohannadarbaji/Documents/Claude Code Obsidian
```

The Write tool **does not expand `~`** — pass the fully-resolved `$VAULT_PATH` for every Write call this session. `~/Documents/...` looks fine in conversation prose but the Write tool will fail with a generic "Error writing file" if you actually pass it. The `obsidian` CLI tolerates `~`; the Write tool does not.

Use `obsidian` CLI commands with `vault="$VAULT_NAME"` for read/create/append. Use the Write tool with the **resolved absolute filesystem path** for overwrites — and Read the file first in this session (Write blocks unread files).

Org folder: the installer also writes `~/.claude/obsidian-org-name` (defaults to `Chalktalk` for back-compat with pre-2026-05 setups; new installs prompt the user). Read it at session start the same way and use `$ORG_NAME` wherever procedures reference `Work/<YourOrg>/...`.

---

## Retrieval Rule — Extract, Don't Traverse

When recalling past work, **extract from the index, don't traverse via LLM**. The vault is the context; queries return matching lines, not whole files. Reading full files just to scan them for a single match burns tokens.

**Backend preference:**
1. **`mcp__qmd__query`** if registered — returns semantically-ranked chunks. Setup: `references/qmd-setup.md`.
2. **`obsidian search:context`** otherwise — BM25 with surrounding context.
3. **`obsidian search`** for filename / wikilink lookups.
4. Use `Read` (or `mcp__qmd__get` / `obsidian read`) on a full file only when you need to **edit** it.

| Wrong (expensive) | Right (cheap) |
|---|---|
| `obsidian search` then Read every match end-to-end | `mcp__qmd__query` or `obsidian search:context` |
| Read full session log to find one decision | Search for the decision text, follow the wikilink to the extracted Decision file |
| Pull every project doc to check priorities | Read `Context/current-focus.md` only |
| Re-read all references "to refresh" | Load only the reference matching the current operation |

If the agent is reading whole files for retrieval rather than searching, it's burning tokens.

## Session-Start Hook

The skill ships a SessionStart hook (`scripts/session-start-context.sh`) that injects vault context (current focus, recent sessions, project listing, git activity) procedurally — no LLM tokens for that work. Wire-up: `references/session-start-hook.md`.

**Hook supplies context. Ritual supplies behavior.** The two are complementary, not redundant:

- If the hook fired this session (you'll see a `## obsidian-memory session-start context` block in the system reminders), the read-context steps are already done — skip steps 1–5 of `references/session-start.md`.
- The behavioral parts (step 6 summary, step 7 weekly vault lint) are NOT covered by the hook. Run those when due.
- If the hook did NOT fire (no context block in the system reminders, or the user didn't wire it up), execute the full `references/session-start.md` ritual including the read steps.

---

## Operations Map

For specific operations, read the matching reference. References load on-demand; this keeps the skill body small.

| What you need to do | Reference |
|---|---|
| Wire up the SessionStart hook (token-cost optimization) | `references/session-start-hook.md` |
| Set up QMD semantic search MCP | `references/qmd-setup.md` |
| Run the session-start ritual (load context) | `references/session-start.md` |
| Run the session-end ritual (update projects, write log, extract decisions/shipping/brag) | `references/session-end.md` |
| Search past work, create project docs, daily notes, quick capture, task tracking, context updates | `references/core-operations.md` |
| Tag competency evidence in session logs | `references/competency-tagging.md` |
| Capture URLs as Source files | `references/source-logging-rules.md` |
| Decide which file-write tool to use (create vs overwrite vs append vs property) | `references/file-operations.md` |
| Vault structure (folder layout, project backlog rules) | `references/vault-structure.md` |
| Project doc update rules (status fields, what gets replaced vs prepended) | `references/project-doc-rules.md` |
| Always-do / ask-first guidelines | `references/guidelines.md` |
| Naming, tags, troubleshooting, skill integration | `references/conventions.md` |
| 7-day vault lint | `references/vault-lint-rules.md` |
| Extracting decisions / shipping / brag content from session logs | `references/extraction-rules.md` |
| Templates for People / Competency / Decision / 1:1 notes | `references/people-template.md`, `competency-template.md`, `decision-template.md`, `one-on-one-template.md` |
| Org chart source for People notes | `references/org-chart-source.md` |
| Future 1:1 import flow (Zoom + Oliv) | `references/future-1on1-import.md` |
| Adopting this skill in your own org | `references/adopting-this-skill.md` |
| Common gotchas | `references/gotchas.md` |
| Installation flow (first-time setup) | `references/installation-flow.md` |

---

## When to Invoke This Skill

**At session start** (every new conversation): read `references/session-start.md` and execute the ritual. If the SessionStart hook injected context (you'll see the block in the system reminders), skip steps 1–5 (read-context) and execute steps 6–7 (summarize, weekly lint) only. Do **not** ask permission — just do it.

**At session end** (when user says "done", "exit", "that's all", "wrap up", or similar): read `references/session-end.md` and execute the ritual. The session-end ritual includes a mandatory approval step before writing project docs.

**Whenever the user asks to recall past work**: search the vault using the retrieval rule above. Do not read whole files when a search would return the answer.

**Throughout the session**: capture URLs as Source files (per `references/source-logging-rules.md`), tag competency evidence in session logs (per `references/competency-tagging.md`), update project docs as work progresses.

---

**Remember**: Project docs are the source of truth for project state. Session logs record what happened on a given date. `Context/current-focus.md` is the dashboard. This skill should work INVISIBLY in the background — the user shouldn't have to think about memory management.
