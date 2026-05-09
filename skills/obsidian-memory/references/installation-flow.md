# Installation Flow (First-Time Only)

Print the following message in the terminal so the user understands what's happening and why:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Setting up Obsidian Memory for Claude Code
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Why Obsidian?
  Claude Code has no memory between sessions by default.
  Every conversation starts from scratch — no context
  about you, your projects, or past decisions.

  Obsidian acts as Claude's persistent brain. At the
  start of each session Claude reads your vault to know
  what you're working on. At the end it saves a session
  log so future sessions pick up where you left off.

  Your notes stay on your machine. No vendor lock-in.
  No tokens consumed storing them in the cloud.

  Step 1: Install Obsidian (if you haven't already)
  → https://obsidian.md  (free download)

  Step 2: Open Obsidian and create a new vault.
  Choose a folder on your machine — for example:
    ~/Documents/Claude Code Obsidian
    ~/Desktop/Claude Code Obsidian
    ~/vaults/my-brain

  The folder name becomes your vault name.

  Step 3: Come back here and tell me the full path
  to your vault folder (e.g. /Users/yourname/Documents/Claude Code Obsidian)
  and I'll finish the setup automatically.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Wait for the user to provide their vault path.

Once they provide the path:

1. **Extract the vault name** (last component of the path):
   ```bash
   VAULT_PATH="/Users/yourname/Documents/Claude Code Obsidian"
   VAULT_NAME=$(basename "$VAULT_PATH")
   echo "$VAULT_NAME"  # e.g. "Claude Code Obsidian"
   ```

2. **Save the vault path AND name** so future sessions don't need setup. The path file is the canonical source of truth (the name file is kept for back-compat with older installs):
   ```bash
   mkdir -p ~/.claude
   echo "$VAULT_PATH" > ~/.claude/obsidian-vault-path
   echo "$VAULT_NAME" > ~/.claude/obsidian-vault-name
   ```

   The path file is what the SessionStart hook and downstream skills read; the name file is a legacy fallback only used if the path file is missing.

3. **Ask the user for their org name** (the folder under `Work/` for org-specific notes — projects, people, decisions, etc.). If they say "skip" or are an individual user, default to `Personal` and skip the next mkdir line:
   ```
   What's your org name? This becomes the folder Work/<OrgName>/Projects/ etc.
   Examples: "Acme", "Stripe", "MyConsulting". Hit enter or say "skip" if
   you don't have one — I'll use Personal.
   ```

   Then save the user's answer. **Substitute the actual value** the user gave you (or "Personal" if they said skip / hit enter):

   ```bash
   ORG_NAME="<the org name the user gave, or 'Personal' if they skipped>"  # e.g. "Acme", "Stripe", "Personal"
   echo "$ORG_NAME" > ~/.claude/obsidian-org-name
   ```

   The placeholder is intentional — do not run the snippet verbatim. The bash `${VAR:-default}` form would silently default to "Personal" because `ORG_NAME` is not set in this shell context. Substitute the literal string before running.

4. **Create the folder structure** the skill expects, parameterized by org name so adopters get their own folders (not "Chalktalk"):
   ```bash
   VAULT="$VAULT_PATH"
   mkdir -p "$VAULT/Sessions/$(date +%Y-%m)"
   mkdir -p "$VAULT/Work/$ORG_NAME/Projects"
   mkdir -p "$VAULT/Personal/Projects"
   mkdir -p "$VAULT/Technical/Learnings"
   mkdir -p "$VAULT/Context"
   touch "$VAULT/Context/current-focus.md"
   touch "$VAULT/Context/preferences.md"
   touch "$VAULT/Context/about-me.md"
   touch "$VAULT/Context/work-context.md"
   # Project Backlog is referenced by session-start.md; create empty so the
   # first session-start ritual doesn't error on a missing-file read.
   touch "$VAULT/Context/Project Backlog.md"
   ```

5. Print confirmation:
   ```
   ✅ Obsidian Memory configured.
      Vault: <VAULT_NAME>
      Vault path: <VAULT_PATH>
      Org folder: Work/<ORG_NAME>/
      Folder structure created.

   Claude will now load context from your vault at the
   start of each session and save session logs at the end.
   ```

6. **Tell the user about the two recommended next steps** (one-time, both are token-cost wins). Skill works fine without either; both fall back gracefully.

   ```
   📌 Recommended next steps (one-time, both optional but recommended):

      1. SessionStart hook — emits vault context procedurally
         instead of via LLM file reads (~3-4x token reduction
         at session start). See:
         skills/obsidian-memory/references/session-start-hook.md

      2. QMD semantic search MCP — adds mcp__qmd__query for
         chunked semantic recall over your vault (BM25 + vector
         embeddings). Falls back to obsidian search:context if
         not registered. See:
         skills/obsidian-memory/references/qmd-setup.md

      Optional org-and-perf adoption (templates for People,
      Decisions, Competencies, etc.):
         skills/obsidian-memory/references/adopting-this-skill.md
   ```

Setup is complete. Continue with normal session start.
