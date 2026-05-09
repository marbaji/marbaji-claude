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

2. **Save the vault name** so future sessions don't need setup:
   ```bash
   echo "Claude Code Obsidian" > ~/.claude/obsidian-vault-name
   ```

3. **Create the folder structure** the skill expects:
   ```bash
   VAULT="$VAULT_PATH"
   mkdir -p "$VAULT/Sessions/$(date +%Y-%m)"
   mkdir -p "$VAULT/Work/Chalktalk/Projects"
   mkdir -p "$VAULT/Personal/Projects"
   mkdir -p "$VAULT/Technical/Learnings"
   mkdir -p "$VAULT/Context"
   touch "$VAULT/Context/current-focus.md"
   touch "$VAULT/Context/preferences.md"
   touch "$VAULT/Context/about-me.md"
   touch "$VAULT/Context/work-context.md"
   ```

4. Print confirmation:
   ```
   ✅ Obsidian Memory configured.
      Vault: <VAULT_NAME>
      Folder structure created.

   Claude will now load context from your vault at the
   start of each session and save session logs at the end.
   ```

5. **Tell the user about the two recommended next steps** (one-time, both are token-cost wins). Skill works fine without either; both fall back gracefully.

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
