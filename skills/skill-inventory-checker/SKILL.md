---
name: skill-inventory-checker
description: Check that all skills are properly symlinked in ~/.claude/skills/ and that marketplace clones are in sync with GitHub. Use when someone says "check my skills", "skill inventory", or "what skills do I have".
---

# Skill Inventory Checker

Verify all skills are healthy: symlinks resolve, clones are in sync with GitHub, and third-party plugins are listed.

## How Skills Work

There are two kinds of skills: **yours** and **third-party**.

### Your Skills

Your skills live in GitHub repos. `claude plugin enable` clones them to your Mac. You symlink from `~/.claude/skills/` into those clones. Claude Code reads `~/.claude/skills/` to populate the `/skill` list. When you edit a skill, you're editing the git repo through the symlink. When you `git pull`, symlinks auto-reflect the changes.

Here's an example with one skill, showing the real paths:

```
github.com/ChalkTalk/claude                                          ← GitHub (remote)
    ↕ git pull / git push
~/.claude/plugins/marketplaces/chalktalk/skills/skills/renewal-storytelling/  ← local git clone
    ↑
    symlink
    |
~/.claude/skills/renewal-storytelling                                ← what Claude Code reads + what you browse/edit
```

Every skill in `~/.claude/skills/` follows this pattern — it's a symlink pointing to a local git clone, which syncs with a GitHub repo.

### Your Repos

| GitHub Repo | Local Clone | Skills Subdirectory |
|---|---|---|
| `ChalkTalk/claude` | `~/.claude/plugins/marketplaces/chalktalk` | `skills/skills/` |
| `marbaji/marbaji-claude` | `~/.claude/plugins/marketplaces/marbaji-claude` | `skills/` |
| `marbaji/private-claude` | `~/.claude/plugins/marketplaces/private-claude` | `skills/` |

External skills (from other repos like `chalktalk-react-40`) also get symlinks in `~/.claude/skills/`, pointing to whatever local checkout has them.

### Third-Party Skills

Third-party skills are managed by `claude plugin update`. They live in `~/.claude/plugins/cache/` and you don't edit them. They're listed at the bottom of the inventory output for reference.

### What the Table Should Look Like

After running this checker, you should see every skill with `✅ symlink` in the `~/.claude/skills` column. That's the healthy state. The Clone column confirms the source files exist. GitHub confirms the remote is reachable.

| Skill | GitHub | Clone | ~/.claude/skills |
|---|---|---|---|
| renewal-storytelling | ✅ | ✅ dir | ✅ symlink |
| obsidian-memory | ✅ | ✅ dir | ✅ symlink |
| atlassian-jira | — | ✅ dir | ✅ symlink |

A `❌ broken` means the symlink target was moved or deleted. A `❌ missing` means the skill exists in the clone but has no symlink. A `dir` (not symlink) means it's a standalone copy that won't auto-update on `git pull`.

---

## Instructions

### Step 1: Discover skills in each location

```bash
# Marketplace clone: ChalkTalk/claude
CHALKTALK_CLONE="$HOME/.claude/plugins/marketplaces/chalktalk/skills/skills"
echo "=== ChalkTalk/claude clone ===" && ls "$CHALKTALK_CLONE" 2>/dev/null

# Marketplace clone: marbaji/marbaji-claude
MARBAJI_CLONE="$HOME/.claude/plugins/marketplaces/marbaji-claude/skills"
echo "=== marbaji/marbaji-claude clone ===" && ls "$MARBAJI_CLONE" 2>/dev/null

# Marketplace clone: marbaji/private-claude
PRIVATE_CLONE="$HOME/.claude/plugins/marketplaces/private-claude/skills"
echo "=== marbaji/private-claude clone ===" && ls "$PRIVATE_CLONE" 2>/dev/null

# ~/.claude/skills
echo "=== ~/.claude/skills ===" && ls -la ~/.claude/skills/ 2>/dev/null
```

### Step 2: Check GitHub sync status

For each marketplace clone, check if it's up to date with GitHub:

```bash
cd ~/.claude/plugins/marketplaces/chalktalk && git fetch --dry-run 2>&1
cd ~/.claude/plugins/marketplaces/marbaji-claude && git fetch --dry-run 2>&1
cd ~/.claude/plugins/marketplaces/private-claude && git fetch --dry-run 2>&1
```

If `git fetch --dry-run` shows output, the clone is behind GitHub.

### Step 3: Classify each entry in ~/.claude/skills/

```bash
for f in ~/.claude/skills/*; do
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
| Skill | GitHub | Clone | ~/.claude/skills |
|---|---|---|---|
```

**Column definitions:**

| Column | What it means | Possible values |
|---|---|---|
| GitHub | Remote repo is reachable and contains this skill | `✅` or `—` (for external skills not in our repos) |
| Clone | Exists in the local git clone on disk | `✅ dir` or empty |
| ~/.claude/skills | Entry in `~/.claude/skills/` | `✅ symlink` / `✅ dir` / `❌ broken` / `❌ missing` |

**Expected healthy state:** GitHub = ✅, Clone = ✅ dir, ~/.claude/skills = ✅ symlink. Any deviation is flagged as an issue.

**Grouping:** Group rows by origin:
1. **ChalkTalk skills** — from `ChalkTalk/claude`
2. **Personal skills (public)** — from `marbaji/marbaji-claude`
3. **Private skills** — from `marbaji/private-claude`
4. **External skills** — from other repos (e.g., chalktalk-react-40)

### Step 5: Flag issues

After the table, list any problems found:

- **Broken symlinks** — point to paths that don't exist (shows as `❌ broken`)
- **Missing from ~/.claude/skills** — skill exists in a clone but has no symlink (shows as `❌ missing`)
- **Standalone copies (`dir`)** — directories in ~/.claude/skills that should be symlinks. These won't auto-update on `git pull`.
- **Clone behind GitHub** — `git fetch --dry-run` showed pending changes

### Step 6: List third-party skills

After the table and issues, list third-party skills grouped by source. These are read-only — managed by `claude plugin update`, not symlinked.

```bash
for dir in ~/.claude/plugins/cache/*/; do
  plugin_org=$(basename "$dir")
  # Skip our repos
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

Format as a non-table list:

```
### Third-Party Skills (read-only, managed by `claude plugin update`)

**claude-plugins-official/superpowers** — 14 skills
  brainstorming, dispatching-parallel-agents, executing-plans, ...

**obsidian-skills/obsidian** — 5 skills
  defuddle, json-canvas, obsidian-bases, obsidian-cli, obsidian-markdown

...
```

### Step 7: Offer fixes

For each issue found, offer a concrete fix command:

- Broken symlink → `rm <broken> && ln -s <clone-path> ~/.claude/skills/<name>`
- Missing symlink → `ln -s <clone-path> ~/.claude/skills/<name>`
- Standalone copy that should be a symlink → `rm -rf <dir> && ln -s <clone-path> ~/.claude/skills/<name>` (confirm with user first — standalone copies may have local changes)
- Clone behind GitHub → `cd <clone-path> && git pull`

Present all fixes and ask the user which ones to apply. Do not auto-apply destructive fixes (removing directories).
