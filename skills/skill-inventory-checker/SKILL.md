---
name: skill-inventory-checker
description: Compare all skills across GitHub repos, Desktop folders, and ~/.claude/skills. Shows what's installed where, detects broken symlinks, missing skills, and stale copies. Use when someone says "check my skills", "skill inventory", or "what skills do I have".
---

# Skill Inventory Checker

Compare all skills across all known locations. Produces a single comparison table showing where each skill lives and how it's linked.

## Locations to Scan

### GitHub Repos (source of truth)

These are the authoritative sources. Skills here are the canonical versions.

| Repo | Local clone path | Skills subdirectory |
|---|---|---|
| `ChalkTalk/claude` | `~/.claude/plugins/marketplaces/chalktalk` | `skills/skills/` |
| `marbaji/marbaji-claude` | `~/.claude/plugins/marketplaces/marbaji-claude` | `skills/` |

### Desktop Folders (organized workspace copies)

| Folder | Purpose |
|---|---|
| `~/Desktop/Claude Code/Skills/chalktalk/` | ChalkTalk skills — should be symlinks to the marketplace clone |
| `~/Desktop/Claude Code/Skills/marbaji/` | Personal skills — should be symlinks to the marketplace clone |

### ~/.claude/skills/ (what Claude Code actually loads)

This is what Claude Code discovers at runtime. Entries here are either:
- **Symlinks** → point to a marketplace clone (auto-updates on `git pull`)
- **Directories** → standalone copies (must be manually updated)

## Instructions

Run all discovery commands, then build the comparison table.

### Step 1: Discover skills in each location

```bash
# GitHub: ChalkTalk/claude
CHALKTALK_REPO="$HOME/.claude/plugins/marketplaces/chalktalk/skills/skills"
echo "=== ChalkTalk/claude ===" && ls "$CHALKTALK_REPO" 2>/dev/null

# GitHub: marbaji/marbaji-claude
MARBAJI_REPO="$HOME/.claude/plugins/marketplaces/marbaji-claude/skills"
echo "=== marbaji/marbaji-claude ===" && ls "$MARBAJI_REPO" 2>/dev/null

# Desktop/chalktalk
DESK_CT="$HOME/Desktop/Claude Code/Skills/chalktalk"
echo "=== Desktop/chalktalk ===" && ls "$DESK_CT" 2>/dev/null

# Desktop/marbaji
DESK_MA="$HOME/Desktop/Claude Code/Skills/marbaji"
echo "=== Desktop/marbaji ===" && ls "$DESK_MA" 2>/dev/null

# ~/.claude/skills
echo "=== ~/.claude/skills ===" && ls ~/.claude/skills/ 2>/dev/null
```

### Step 2: Classify each entry

For every entry in `Desktop/` and `~/.claude/skills/`, determine its type:

```bash
# For each entry in a directory:
for f in "$DIR"/*; do
  name="$(basename "$f")"
  if [ -L "$f" ]; then
    target="$(readlink "$f")"
    if [ -e "$f" ]; then
      echo "symlink -> $target"
    else
      echo "BROKEN symlink -> $target"
    fi
  elif [ -d "$f" ]; then
    echo "directory (standalone copy)"
  fi
done
```

### Step 3: Build comparison table

Produce this table, with one row per unique skill name across all locations:

```
| Skill | ChalkTalk/claude | Desktop/chalktalk | marbaji/marbaji-claude | Desktop/marbaji | ~/.claude/skills |
|---|---|---|---|---|---|
```

**Column values:**

| Location | Possible values |
|---|---|
| GitHub repos | `✅` (exists) or empty |
| Desktop folders | `✅ symlink` / `✅ dir` (standalone copy) / `❌ broken` / empty |
| ~/.claude/skills | `✅ symlink` / `✅ dir` / `❌ broken` / empty |

**Grouping:** Group rows by origin repo:
1. **ChalkTalk skills** — any skill that exists in `ChalkTalk/claude`
2. **Personal skills** — any skill that exists in `marbaji/marbaji-claude`
3. **Untracked** — skills in `~/.claude/skills/` or Desktop that aren't in either GitHub repo

### Step 4: Flag issues

After the table, list any problems found:

- **Broken symlinks** — point to paths that don't exist
- **Missing from Desktop** — on GitHub but not in the corresponding Desktop folder
- **Missing from ~/.claude/skills** — on GitHub but not loadable by Claude Code
- **Standalone copies** — directories in Desktop or ~/.claude/skills that could be symlinks to the marketplace clone (won't auto-update)
- **Untracked skills** — in ~/.claude/skills or Desktop but not in any GitHub repo

### Step 5: Offer fixes

For each issue found, offer a concrete fix command:

- Broken symlink → `rm <broken> && ln -s <correct-target> <name>`
- Missing from Desktop → `ln -s <marketplace-path> "<desktop-path>/<name>"`
- Missing from ~/.claude/skills → `ln -s <marketplace-path> ~/.claude/skills/<name>`
- Standalone copy that should be a symlink → `rm -rf <dir> && ln -s <marketplace-path> <name>` (confirm with user first — standalone copies may have local changes)

Present all fixes and ask the user which ones to apply. Do not auto-apply destructive fixes (removing directories).
