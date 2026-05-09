# Core Operations (Search, Project Docs, Daily, Capture, Tasks, Context)

## Search Past Work

**When to use**: User asks "what did we do about X" or "find sessions where we worked on Y".

Apply the retrieval rule from SKILL.md: extract from the index, don't traverse. Prefer `search:context` (matching lines only) over `search` followed by full-file reads.

```bash
# Search all content
obsidian search query="<search-term>" vault="<VAULT_NAME>"

# Search with context (shows matching lines)
obsidian search:context query="<search-term>" vault="<VAULT_NAME>"

# Search by tags
obsidian tags vault="<VAULT_NAME>"
obsidian tag name="<tag-name>" vault="<VAULT_NAME>"

# Find related sessions
obsidian backlinks file="<note-name>" vault="<VAULT_NAME>"
```

## Create Project Documentation

**When to use**: User starts a new project or wants to document existing work (can also happen mid-session, not just at session end).

1. Determine category (ChalkTalk → `Work/Chalktalk/Projects/`, Personal → `Personal/Projects/<Name>/`)
2. Create project doc with overview, status, key details, next steps
3. Update current-focus to reference new project

## Daily Note

**When to use**: User wants to see today's activity or add quick notes.

```bash
obsidian daily vault="<VAULT_NAME>"
obsidian daily:append content="- <note-text>" vault="<VAULT_NAME>"
obsidian daily:read vault="<VAULT_NAME>"
```

## Quick Capture

**When to use**: User has an idea, decision, or learning to capture.

```bash
# Capture idea
obsidian create \
  name="<idea-title>" \
  path="Personal/Ideas/<idea-name>.md" \
  vault="<VAULT_NAME>"

# Capture learning
obsidian append \
  file="Technical/Learnings/lessons-learned" \
  content="\n## $(date +%Y-%m-%d): <learning>\n<details>\n" \
  vault="<VAULT_NAME>"
```

## Task Management

**When to use**: User wants to track tasks across sessions.

```bash
obsidian tasks vault="<VAULT_NAME>"
obsidian tasks todo vault="<VAULT_NAME>"
obsidian tasks file="Context/current-focus" vault="<VAULT_NAME>"
obsidian task file="<file>" line=<line-number> toggle vault="<VAULT_NAME>"
```

## Context Updates

**When to use**: User's role, focus, or preferences change.

Read then update the relevant context file. Note: `obsidian update` does not exist. To overwrite a file, use the Write tool targeting the vault path directly. See `references/file-operations.md`.

## Source Logging — Capture URLs with Context

**When to use**: During any save ritual (session end, "log progress," mid-session save) when URLs were shared in the conversation.

If URLs were shared, read `references/source-logging-rules.md` and follow it. It defines the source file format, two-layer source system (raw Sources/ → aggregated Knowledge/ pages), and naming conventions.
