# QMD Semantic Search Setup

QMD is the recommended semantic-search backend for vault retrieval. Once installed and registered as an MCP server, the agent gains `mcp__qmd__query`, `mcp__qmd__get`, and `mcp__qmd__multi_get` for chunked semantic recall. Without QMD, the skill falls back to `obsidian search:context` (BM25 only) — works fine, just less precise on conceptual queries.

Same backend used by the breferrari/obsidian-mind reference architecture.

---

## Why QMD over `obsidian search`

| Feature | `obsidian search` | QMD |
|---|---|---|
| Lexical match | Yes | Yes (BM25) |
| Semantic match | No | Yes (embeddings) |
| Returns matching chunks (not whole files) | `search:context` only | Always |
| Reranking | No | Optional LLM rerank (large model) |
| Persistent index | No (greps each query) | Yes (SQLite) |
| Per-query cost | File scan of vault | Embedding lookup |

For a vault past ~50-100 sessions, semantic match meaningfully improves recall — finds "what did we decide about caching" even when the note is titled "Redis Migration ADR."

---

## Installation (one-time)

```bash
npm install -g @tobilu/qmd
```

QMD ships as the binary `qmd`. Verify:

```bash
qmd --version
# qmd 2.1.0 (or later)
```

## Add your vault as a collection

```bash
# Resolve the vault path from the canonical config (path-file preferred,
# name-file legacy fallback for pre-2026-05 setups).
VAULT_PATH="$(cat ~/.claude/obsidian-vault-path 2>/dev/null)"
if [[ -z "$VAULT_PATH" ]]; then
  VAULT_NAME="$(cat ~/.claude/obsidian-vault-name 2>/dev/null)"
  [[ -n "$VAULT_NAME" ]] && VAULT_PATH="$HOME/Documents/$VAULT_NAME"
fi

qmd collection add "$VAULT_PATH" --name obsidian-memory
```

This indexes every `**/*.md` file under the vault path. Verify:

```bash
qmd status
# Documents
#   Total:    288 files indexed
#   Vectors:  0 embedded
#   Pending:  288 need embedding (run 'qmd embed')
```

## Build embeddings

```bash
qmd embed
```

First-time embed downloads the embedding model (about 333MB) and embeds every chunk. On Apple Silicon with Metal GPU, ~880 chunks across ~300 files completes in under a minute.

**Optional: download the larger query-expansion / rerank model** (about 1.28GB) if you want `qmd query` (hybrid expand + rerank). Use `qmd search` (BM25 only) or `qmd vsearch` (semantic only) to skip the larger download.

## Register as an MCP server in Claude Code

```bash
claude mcp add --scope user qmd qmd mcp
```

This adds an entry to `~/.claude.json` (Claude Code's user-scope MCP config). Verify:

```bash
claude mcp get qmd
# qmd:
#   Scope: User config (available in all your projects)
#   Status: ✓ Connected
#   Type: stdio
#   Command: qmd
#   Args: mcp
```

> Note: `~/.claude/.mcp.json` is **not** read by Claude Code. The actual user config lives at `~/.claude.json` and is managed by `claude mcp add`. Project-scoped `.mcp.json` files in a repo root work, but for vault retrieval you want user scope.

Restart Claude Code so the new MCP tools (`mcp__qmd__query`, `mcp__qmd__get`, `mcp__qmd__multi_get`) appear in the agent's tool menu.

---

## Using QMD from the skill

The retrieval rule in SKILL.md instructs the agent to prefer `mcp__qmd__query` over `obsidian search` when QMD is registered. If QMD is not registered, the agent falls back to `obsidian search:context` and `obsidian search`. Either path returns matching content, not whole files — this is the "extract from index, don't traverse" rule.

Example query:

```
mcp__qmd__query(query="what did we decide about caching")
```

Returns ranked chunks with file paths and surrounding context. The agent may then `mcp__qmd__get` (or `Read`) a specific file only if it needs to edit it.

---

## Re-indexing cadence

- After bulk edits to existing files: `qmd update` (incremental)
- After adding many new notes: `qmd update` is usually sufficient; `qmd embed -f` for a full rebuild
- One-shot updates (single file edited): no action needed; QMD re-checks on query if the index is older than the file

You can wire this into the SessionStart hook if you want auto-updates, but `qmd update` can take 10-30 seconds on a large vault — slowing every session start.

---

## Multiple collections

You can index more than one folder. Common pattern: vault as one collection, codebase as another.

```bash
qmd collection add ~/code/some-repo --name some-repo
qmd collection list
qmd collection exclude some-repo   # exclude from default queries
```

When `mcp__qmd__query` runs without a collection filter, it searches all included collections. Use the `-c <name>` flag from the CLI to restrict.

---

## Fallback behavior

The skill works fine without QMD. The agent uses `obsidian search:context` and `obsidian search` for retrieval. You'll see less precise hits on conceptual queries, but file lookups by name or exact phrase still work as expected.

If you decide QMD isn't worth the setup (small vault, infrequent recall queries), skipping it is a defensible choice.
