---
name: skill-inventory-checker
description: Audit installed skills — check that marketplace clones are in sync with GitHub, and detect any duplicate copies in ~/.claude/skills/ that should be retired. Use when someone says "check my skills", "skill inventory", or "what skills do I have".
---

# Skill Inventory Checker

Verify all skills are healthy: marketplace clones are in sync with GitHub, no duplicate personal copies of plugin skills exist, and third-party plugins are listed.

## How Skills Work

Skills are distributed through **plugin marketplaces** — git repos that bundle skills, hooks, slash commands, and MCP server configs. Claude Code reads skills directly from marketplace clones; you do not need to copy them into `~/.claude/skills/`.

### The single-source-of-truth model

```
github.com/<org>/<repo>                                            ← GitHub (remote)
    ↕ git pull / git push
~/.claude/plugins/marketplaces/<name>/skills/<skill>/SKILL.md      ← local clone, registered via marketplace.json
                                                                     Claude Code loads this as /<plugin>:<skill>
```

That's it. No symlinks, no duplicates. Editing the file in the clone is editing the git repo. `git pull` (or marketplace pull) refreshes everything atomically.

### When to use ~/.claude/skills/

Only for skills that are **not** in any marketplace — drafts, experiments, or skills you want to keep purely local. Anything published in a marketplace should NOT also live in `~/.claude/skills/`; the duplicate adds a redundant `/<skill>` slash command alongside the proper `/<plugin>:<skill>`, and on macOS APFS the duplicate is often clone-linked back to the marketplace clone, causing edits in `~/.claude/skills/` to bleed silently into the marketplace working tree.

### Your repos

| GitHub Repo | Local Clone | Skills Subdirectory |
|---|---|---|
| `ChalkTalk/claude` | `~/.claude/plugins/marketplaces/chalktalk` | `skills/skills/` |
| `marbaji/marbaji-claude` | `~/.claude/plugins/marketplaces/marbaji-claude` | `skills/` |
| `marbaji/private-claude` | `~/.claude/plugins/marketplaces/private-claude` | `skills/` |

### Third-party skills

Third-party skills come from other marketplaces (`claude-plugins-official`, `superpowers-marketplace`, `obsidian-skills`, etc.) and are listed at the bottom of the inventory output for reference. They're managed by `claude plugin update` and should never need a copy in `~/.claude/skills/`.

---

## Instructions

### Step 0: Print the explainer

Before any tables, print the "How Skills Work" section above verbatim. The user needs the single-source-of-truth model to understand why duplicates in `~/.claude/skills/` are a problem.

### Step 1: Discover skills in each marketplace clone

```bash
echo "=== ChalkTalk/claude clone ===" && ls "$HOME/.claude/plugins/marketplaces/chalktalk/skills/skills" 2>/dev/null
echo "=== marbaji/marbaji-claude clone ===" && ls "$HOME/.claude/plugins/marketplaces/marbaji-claude/skills" 2>/dev/null
echo "=== marbaji/private-claude clone ===" && ls "$HOME/.claude/plugins/marketplaces/private-claude/skills" 2>/dev/null
echo "=== ~/.claude/skills (should only contain truly local skills) ==="
ls -la ~/.claude/skills/ 2>/dev/null
```

### Step 2: Check GitHub sync status

For each marketplace clone, check if it's up to date with GitHub:

```bash
cd ~/.claude/plugins/marketplaces/chalktalk && git fetch --dry-run 2>&1
cd ~/.claude/plugins/marketplaces/marbaji-claude && git fetch --dry-run 2>&1
cd ~/.claude/plugins/marketplaces/private-claude && git fetch --dry-run 2>&1
```

If `git fetch --dry-run` shows output, the clone is behind GitHub. Check for uncommitted local changes too — those are usually hardlink/clonefile bleed from a `~/.claude/skills/` duplicate and should be discarded after confirming with the user.

### Step 3: Detect personal duplicates of marketplace skills

Walk each entry in `~/.claude/skills/` and check whether a same-named skill exists in any marketplace clone:

```bash
for f in ~/.claude/skills/*; do
  name="$(basename "$f")"
  [ -f "$f/SKILL.md" ] || continue
  match=$(find ~/.claude/plugins/marketplaces -maxdepth 5 -type d -name "$name" 2>/dev/null | grep -E "/skills(/skills)?/$name$" | head -1)
  if [ -n "$match" ]; then
    echo "DUPLICATE  $name  →  $match"
  else
    echo "LOCAL-ONLY $name  (no marketplace counterpart — OK to keep)"
  fi
done
```

Anything tagged `DUPLICATE` should be retired from `~/.claude/skills/`. Anything tagged `LOCAL-ONLY` is a genuinely-local skill and stays.

### Step 4: Build comparison table

Produce one row per unique skill name across all locations:

```
| Skill | GitHub | Marketplace clone | ~/.claude/skills |
|---|---|---|---|
```

**Column definitions:**

| Column | What it means | Possible values |
|---|---|---|
| GitHub | Remote repo is reachable and contains this skill | `✅` or `—` (for local-only skills) |
| Marketplace clone | Exists in the marketplace clone on disk | `✅` or empty |
| ~/.claude/skills | Entry in `~/.claude/skills/` | `❌ duplicate` (in marketplace too — should be deleted) / `✅ local-only` (no marketplace counterpart, OK) / empty (the healthy default for marketplace skills) |

**Expected healthy state for a marketplace skill:** GitHub = ✅, Marketplace clone = ✅, `~/.claude/skills` = empty. A `❌ duplicate` row is the issue this skill is here to flag.

**Grouping:** Group rows by origin:
1. **ChalkTalk skills** — from `ChalkTalk/claude`
2. **Personal skills (public)** — from `marbaji/marbaji-claude`
3. **Private skills** — from `marbaji/private-claude`
4. **Third-party skills** — from other marketplaces (read-only)
5. **Local-only skills** — in `~/.claude/skills/` with no marketplace counterpart

### Step 5: Flag issues

After the table, list any problems found:

- **Personal duplicate of marketplace skill** — `~/.claude/skills/<name>/` exists AND `<name>` is in a marketplace clone. Recommend `rm -rf ~/.claude/skills/<name>` (the marketplace registration provides `/<plugin>:<name>`; the personal duplicate registers a redundant `/<name>` and risks edit-bleed via APFS clones).
- **Marketplace clone behind GitHub** — `git fetch --dry-run` showed pending changes; recommend `git pull` in the clone.
- **Marketplace clone has uncommitted changes** — usually hardlink/clonefile bleed from a personal duplicate; recommend confirming with the user before discarding.

### Step 6: List third-party skills

After the table and issues, list third-party skills grouped by source. These are read-only — managed by `claude plugin update`.

```bash
for dir in ~/.claude/plugins/cache/*/; do
  plugin_org=$(basename "$dir")
  case "$plugin_org" in chalktalk|marbaji-claude|private-claude) continue ;; esac
  for plugin_dir in "$dir"*/; do
    plugin_name=$(basename "$plugin_dir")
    for version_dir in "$plugin_dir"*/; do
      skills_dir="$version_dir/skills"
      if [ -d "$skills_dir" ]; then
        echo ""
        echo "**$plugin_org/$plugin_name** — $(ls "$skills_dir" | wc -l | tr -d ' ') skills"
        ls "$skills_dir" | sed 's/^/  /'
      fi
    done
  done
done
```

### Step 7: Offer fixes

For each issue found, offer a concrete fix command:

- Personal duplicate of marketplace skill → `rm -rf ~/.claude/skills/<name>` (confirm with user; check for any uncommitted local edits via `diff -r ~/.claude/skills/<name> <marketplace-clone>/<name>` first)
- Marketplace clone behind GitHub → `cd <clone-path> && git pull`
- Marketplace clone has uncommitted changes → show the diff, then `cd <clone-path> && git checkout HEAD -- <files>` or `git stash` based on user choice

Present all fixes and ask the user which ones to apply. Do not auto-apply destructive fixes — duplicates may have local edits the user wants to harvest into the marketplace before deletion.
