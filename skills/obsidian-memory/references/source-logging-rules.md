# Source Logging — Capture URLs with Context

Run this during any save ritual (session end, "log progress," mid-session save) when URLs were shared in the conversation.

## The Rule: Sources/ Files Come First, Session Log Bullets Are Derived

The session log's `## Sources Captured` section is **a derived artifact**. Never hand-type URL bullets into it. Always:

1. Enumerate every URL shared this session.
2. **Create a `Sources/YYYY-MM-DD-name.md` file for each one first.**
3. **Then** generate the session log's `Sources Captured` section by listing the files you just created as wikilinks.

Inverting this order (writing URLs into the session log and *intending* to create source files later) is the failure mode that caused multiple missed sources historically. A PostToolUse hook at `~/.claude/hooks/check-session-log-sources.py` enforces this rule by blocking writes to session logs that reference missing `Sources/` files or contain raw URL bullets.

## Steps

### 1. Enumerate URLs

Scroll the current conversation (or the since-last-save window). List every URL that was shared — including ones shared only in passing. If an article cites another article that shaped the discussion, that counts too.

### 2. Create one `Sources/` file per URL

```bash
obsidian create \
  path="Sources/YYYY-MM-DD-descriptive-name.md" \
  content="<source-doc>" \
  vault="<VAULT_NAME>"
```

**Source file format:**
```markdown
---
date: YYYY-MM-DD
url: <original-url>
type: <article|github-gist|video|documentation|social-post|tool>
tags: [relevant, tags]
---

# Descriptive Title

## Summary
Objective description of what the source says. 2-4 sentences.

## Takeaways
Personal learnings and insights extracted from this source.
What's useful for our work? What changes how we think?
- Takeaway 1
- Takeaway 2

## Context
Discussed in [[Sessions/YYYY-MM/YYYY-MM-DD-session-topic]]
Brief note on how/why this source came up.
```

If a URL is paywalled or JS-gated (X/Twitter, LinkedIn, Substack): use Playwright CLI (`playwright screenshot --full-page <url> /tmp/out.png`), then read the image to transcribe content before creating the source file. Never skip a source because WebFetch failed — fall back to the screenshot path.

### 3. Generate the session log's `Sources Captured` section from the files you just created

Only after every source file exists, add this section to the session log:

```markdown
## Sources Captured
- [[Sources/YYYY-MM-DD-descriptive-name|Title]] — why it was relevant
```

Every bullet must be a `[[Sources/...]]` wikilink to a file that exists. No raw URLs. The PostToolUse hook will block the write if this is violated.

## Two-Layer Source System

- **Sources/** is the raw citation library. One file per URL. Grows automatically.
- **Aggregated project pages** (e.g., `Work/Chalktalk/Knowledge/skill-architecture-sources.md`) are curated per-project views that roll up relevant sources with analysis. These are what the user reads.

Sources/ is the raw layer feeding the aggregated pages. When multiple sources relate to a project, roll them up into the appropriate aggregated page if one exists.

## Where Aggregated Pages Live

Curated multi-source knowledge pages go under `Work/Chalktalk/Knowledge/` (for work topics) or `Personal/Knowledge/` (for personal topics). These are knowledge artifacts — distinct from project docs (which track work) and session logs (which track what happened). Example: `Work/Chalktalk/Knowledge/skill-architecture-sources.md` aggregates 5+ sources about agent architecture into one reference page.

## Naming

Use a short descriptive name derived from the content (like the Instagram transcription skill does). Title case, under ~60 chars, hyphens for spaces in the filename.
