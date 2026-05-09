# QMD Semantic Search Setup

QMD is the recommended semantic-search backend for vault retrieval. It registers as an MCP server, exposing `mcp__qmd__query`, `mcp__qmd__get`, and `mcp__qmd__multi_get` to the agent. Without QMD, the skill falls back to `obsidian search` (BM25-only) which works fine but is less precise.

This is the same backend used by the breferrari/obsidian-mind reference architecture.

---

## Why QMD over `obsidian search`

| Feature | `obsidian search` | QMD |
|---|---|---|
| Lexical match | Yes | Yes (BM25) |
| Semantic match | No | Yes (embeddings) |
| Returns matching chunks (not whole files) | `search:context` only | Always |
| Reranking | No | Optional LLM rerank |
| Persistent index | No (greps each query) | Yes (SQLite) |
| Per-query cost | File scan of vault | Embedding lookup |

For a vault that grows past ~50-100 sessions, semantic match meaningfully improves recall — finding "what did we decide about caching" even when the note is titled "Redis Migration ADR."

## Installation (one-time)

```bash
npm install -g @tobilu/qmd
```

First-time `qmd embed` downloads a ~328MB embedding model. `qmd query` (with LLM reranking) downloads an additional ~1.28GB model on first use. Use `qmd search` (BM25) or `qmd vsearch` (semantic only) to skip the larger download if you want to stay lightweight.

## Bootstrap the vault index

QMD needs to know what to index. Create or edit a `vault-manifest.json` at your vault root:

```json
{
  "qmd_index": "obsidian-memory",
  "qmd_context": [
    "Sessions/**/*.md",
    "Work/**/*.md",
    "Personal/**/*.md",
    "Context/**/*.md",
    "Sources/**/*.md"
  ]
}
```

Then build the index:

```bash
cd ~/Documents/<VAULT_NAME>
qmd --index obsidian-memory embed
```

This creates a SQLite store and embeds the listed files. Re-run after bulk edits or many new notes:

```bash
qmd --index obsidian-memory update   # incremental
qmd --index obsidian-memory embed    # full rebuild
```

## Register as an MCP server

Add to `~/.claude/.mcp.json` (or your shell-level Claude Code MCP config):

```json
{
  "mcpServers": {
    "qmd": {
      "command": "qmd",
      "args": ["--index", "obsidian-memory", "mcp"]
    }
  }
}
```

Restart Claude Code. Verify registration:

```bash
claude mcp list | grep qmd
```

The agent should now see `mcp__qmd__query`, `mcp__qmd__get`, `mcp__qmd__multi_get` in its tool menu alongside Read, Edit, etc.

## Using QMD from the skill

The retrieval rule in SKILL.md instructs the agent to prefer `mcp__qmd__query` over `obsidian search` when QMD is registered. If QMD is not registered, the agent falls back to `obsidian search:context` and `obsidian search`. Either path returns matching content, not whole files — this is the "extract from index, don't traverse" rule.

Example query:

```
mcp__qmd__query(
  query="what did we decide about caching",
  limit=5
)
```

Returns ranked chunks with file paths and surrounding context. The agent may then `mcp__qmd__get` (or `Read`) a specific file only if it needs to edit it.

## Re-indexing cadence

- After bulk edits to existing files: `qmd update`
- After adding many new notes (>20): `qmd embed` (full rebuild) or `qmd update`
- One-shot updates (single file edited): no action needed; QMD re-checks on query if the index is older than the file

You can wire this into the SessionStart hook if you want auto-updates, but be aware `qmd update` can take 10-30 seconds on a large vault — slowing every session start.

## Fallback behavior

The skill works fine without QMD. The agent uses `obsidian search:context` and `obsidian search` for retrieval. You'll see less precise hits on conceptual queries, but file lookups by name or exact phrase still work as expected.

If you decide QMD isn't worth the setup (small vault, infrequent recall queries), skipping it is a defensible choice.
