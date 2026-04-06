# Source Logging — Capture URLs with Context

Run this during any save ritual (session end, "log progress," mid-session save) when URLs were shared in the conversation.

## What to Do

1. Identify all URLs shared during the session (or since last save)
2. For each URL, create a source file in the vault:

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

3. In the session log, add a "Sources Captured" section listing the URLs captured:
   ```markdown
   ## Sources Captured
   - [[Sources/YYYY-MM-DD-descriptive-name|Title]] — why it was relevant
   ```

## Two-Layer Source System

- **Sources/** is the raw citation library. One file per URL. Grows automatically.
- **Aggregated project pages** (e.g., `Work/Chalktalk/Knowledge/skill-architecture-sources.md`) are curated per-project views that roll up relevant sources with analysis. These are what the user reads.

Sources/ is the raw layer feeding the aggregated pages. When multiple sources relate to a project, roll them up into the appropriate aggregated page if one exists.

## Where Aggregated Pages Live

Curated multi-source knowledge pages go under `Work/Chalktalk/Knowledge/` (for work topics) or `Personal/Knowledge/` (for personal topics). These are knowledge artifacts — distinct from project docs (which track work) and session logs (which track what happened). Example: `Work/Chalktalk/Knowledge/skill-architecture-sources.md` aggregates 5+ sources about agent architecture into one reference page.

## Naming

Use a short descriptive name derived from the content (like the Instagram transcription skill does). Title case, under ~60 chars, hyphens for spaces in the filename.
