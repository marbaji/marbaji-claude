---
name: skill-inventory-checker
description: Compare all skills across GitHub repos, local clones, Desktop folders, and ~/.claude/skills. Shows what's installed where, detects broken symlinks, missing skills, and stale copies. Use when someone says "check my skills", "skill inventory", or "what skills do I have".
---

# Skill Inventory Checker

Compare all skills across all known locations. Produces a single comparison table showing where each skill lives and how it's linked.

## How Skills Flow

```
GitHub (remote repo)           ← source of truth, the code on github.com
    ↓  git pull / claude plugin enable
Marketplace clone (local)      ← the ONLY real copy of files on disk
    ↑           ↑
 symlink     symlink
    |           |
Desktop/     ~/.claude/skills/ ← pointers, not copies
```

- **GitHub** — the remote repo on github.com. The canonical version.
- **Marketplace clone** — the local `git clone` managed by `claude plugin enable`. This is where the actual files live on disk. Everything else should be a symlink pointing here.
- **Desktop/Skills/** — organized workspace for browsing/editing. Should be symlinks into the marketplace clone.
- **~/.claude/skills/** — what Claude Code loads at runtime. Should be symlinks into the marketplace clone. If a skill isn't here, Claude can't use it.

## Locations to Scan

### GitHub Repos → Marketplace Clones

| GitHub Repo (remote) | Marketplace Clone (local) | Skills subdirectory |
|---|---|---|
| `ChalkTalk/claude` | `~/.claude/plugins/marketplaces/chalktalk` | `skills/skills/` |
| `marbaji/marbaji-claude` | `~/.claude/plugins/marketplaces/marbaji-claude` | `skills/` |

### Desktop Folders

| Folder | Should contain |
|---|---|
| `~/Desktop/Claude Code/Skills/chalktalk/` | Symlinks → chalktalk marketplace clone |
| `~/Desktop/Claude Code/Skills/marbaji/` | Symlinks → marbaji marketplace clone |

### ~/.claude/skills/ (Claude Code runtime)

Entries here are either:
- **Symlinks** → point to a marketplace clone (auto-updates on `git pull`)
- **Directories** → standalone copies (must be manually updated, won't auto-update)

## Instructions

Run all discovery commands, then build the comparison table.

### Step 1: Discover skills in each location

```bash
# Marketplace clone: ChalkTalk/claude
CHALKTALK_CLONE="$HOME/.claude/plugins/marketplaces/chalktalk/skills/skills"
echo "=== ChalkTalk/claude clone ===" && ls "$CHALKTALK_CLONE" 2>/dev/null

# Marketplace clone: marbaji/marbaji-claude
MARBAJI_CLONE="$HOME/.claude/plugins/marketplaces/marbaji-claude/skills"
echo "=== marbaji/marbaji-claude clone ===" && ls "$MARBAJI_CLONE" 2>/dev/null

# Desktop/chalktalk
DESK_CT="$HOME/Desktop/Claude Code/Skills/chalktalk"
echo "=== Desktop/chalktalk ===" && ls "$DESK_CT" 2>/dev/null

# Desktop/marbaji
DESK_MA="$HOME/Desktop/Claude Code/Skills/marbaji"
echo "=== Desktop/marbaji ===" && ls "$DESK_MA" 2>/dev/null

# ~/.claude/skills
echo "=== ~/.claude/skills ===" && ls ~/.claude/skills/ 2>/dev/null
```

### Step 2: Check GitHub sync status

For each marketplace clone, check if it's up to date with GitHub:

```bash
cd ~/.claude/plugins/marketplaces/chalktalk && git fetch --dry-run 2>&1
cd ~/.claude/plugins/marketplaces/marbaji-claude && git fetch --dry-run 2>&1
```

If `git fetch --dry-run` shows output, the clone is behind GitHub.

### Step 3: Classify each entry

For every entry in `Desktop/` and `~/.claude/skills/`, determine its type:

```bash
# For each entry in a directory:
for f in "$DIR"/*; do
  name="$(basename "$f")"
  if [ -L "$f" ]; then
    target="$(readlink "$f")"
    if [ -e "$f" ]; then
      echo "$name|symlink|$target"
    else
      echo "$name|BROKEN|$target"
    fi
  elif [ -d "$f" ]; then
    echo "$name|dir|"
  fi
done
```

### Step 4: Build comparison table

Produce this table, with one row per unique skill name across all locations:

```
| Skill | GitHub | Clone | Desktop | ~/.claude/skills |
|---|---|---|---|---|
```

**Column definitions:**

| Column | What it means | Possible values |
|---|---|---|
| GitHub | Exists in the remote repo on github.com | `✅` or empty |
| Clone | Exists in the local marketplace clone (the real files) | `✅ dir` (always a dir — this is where files live) or empty |
| Desktop | Entry in `~/Desktop/Claude Code/Skills/` | `✅ symlink` / `✅ dir` / `❌ broken` / empty |
| ~/.claude/skills | Entry in `~/.claude/skills/` (what Claude loads) | `✅ symlink` / `✅ dir` / `❌ broken` / empty |

**Expected healthy state:** GitHub = ✅, Clone = ✅ dir, Desktop = ✅ symlink, ~/.claude/skills = ✅ symlink. Any deviation is flagged as an issue.

**Scope:** This inventory only tracks skills from our two repos (`ChalkTalk/claude` and `marbaji/marbaji-claude`). Third-party skills (superpowers, code-review, document-skills, excalidraw-diagram, etc.) are managed by their own marketplace plugins and are out of scope — ignore them.

**Grouping:** Group rows by origin repo:
1. **ChalkTalk skills** — any skill that exists in `ChalkTalk/claude`
2. **Personal skills** — any skill that exists in `marbaji/marbaji-claude`

When classifying entries in `~/.claude/skills/` and Desktop, skip any entry whose symlink target points outside our two marketplace clones, or any standalone directory that doesn't match a skill name in either repo.

### Step 5: Flag issues

After the table, list any problems found:

- **Broken symlinks** — point to paths that don't exist (shows as `❌ broken`)
- **Missing from Desktop** — in Clone but no Desktop entry
- **Missing from ~/.claude/skills** — in Clone but Claude Code can't load it
- **Standalone copies (`dir`)** — directories in Desktop or ~/.claude/skills that should be symlinks. These won't auto-update when you `git pull` the clone.
- **Clone behind GitHub** — `git fetch --dry-run` showed pending changes

### Step 6: Offer fixes

For each issue found, offer a concrete fix command:

- Broken symlink → `rm <broken> && ln -s <clone-path> <name>`
- Missing from Desktop → `ln -s <clone-path> "<desktop-path>/<name>"`
- Missing from ~/.claude/skills → `ln -s <clone-path> ~/.claude/skills/<name>`
- Standalone copy that should be a symlink → `rm -rf <dir> && ln -s <clone-path> <name>` (confirm with user first — standalone copies may have local changes)
- Clone behind GitHub → `cd <clone-path> && git pull`

Present all fixes and ask the user which ones to apply. Do not auto-apply destructive fixes (removing directories).
