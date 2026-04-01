---
name: skill-inventory-checker
description: Compare all skills across GitHub repos, local clones, Desktop folders, ~/.claude/skills, and plugin caches. Shows what's installed where, detects broken symlinks, missing skills, stale copies, and stale plugin caches. Use when someone says "check my skills", "skill inventory", or "what skills do I have".
---

# Skill Inventory Checker

Compare all skills across all known locations. Produces a single comparison table showing where each skill lives and how it's linked.

## How Skills Flow

```
GitHub (remote repo)             ← source of truth, the code on github.com
    ↓  git pull / claude plugin enable
Marketplace clone (local)        ← the ONLY real copy of files on disk
    ↑           ↑           ↓
 symlink     symlink     manual sync / plugin update
    |           |           ↓
Desktop/     ~/.claude/   Plugin cache (~/.claude/plugins/cache/)
             skills/      ← what Claude Code ACTUALLY loads for the skills list
```

- **GitHub** — the remote repo on github.com. The canonical version.
- **Marketplace clone** — the local `git clone` managed by `claude plugin enable`. This is where the actual files live on disk. Everything else should be a symlink pointing here.
- **Plugin cache** — a snapshot of skills copied into `~/.claude/plugins/cache/` at install time. **This is what Claude Code reads to populate the `/skill` list.** It does NOT auto-update when you push to GitHub or edit the marketplace clone. Cache staleness is the #1 cause of skills "disappearing" or running outdated versions.
- **Desktop/Skills/** — organized workspace for browsing/editing. Should be symlinks into the marketplace clone. Also serves as a convenience layer so all skills are visible in the project folder, making them easy to read and edit without navigating to the marketplace clone paths.
- **~/.claude/skills/** — additional skill loading path. Should be symlinks into the marketplace clone.

## Output Column Definitions

The comparison table has four columns. Here's what each one means:

| Column | What it represents | Healthy state |
|---|---|---|
| **Clone** | The local git clone of the marketplace repo (e.g., `~/.claude/plugins/marketplaces/chalktalk/`). This is the source of truth on disk — where you edit skill files and push changes to GitHub. | `✅ dir` |
| **Cache** | Claude Code's internal plugin cache at `~/.claude/plugins/cache/`. When you install a marketplace plugin, Claude Code copies skills here for fast loading. **This is what Claude Code actually reads to populate the `/skill` list.** It does NOT auto-update when you push to GitHub or edit the marketplace clone. | `✅ cached` |
| **Desktop** | The current project directory (`~/Desktop/Claude Code/Skills/`). These are symlinks pointing back to the clone directory. Makes skills available in the project context and keeps them visible in the project folder for easy reading and editing. | `✅ symlink` |
| **~/.claude/skills** | The global user-level skills directory. Skills placed here are available in every project regardless of working directory. An alternative to per-project Desktop symlinks for skills you want everywhere. | `✅ symlink` |

A dash (`—`) means the skill isn't present in that location (which may be fine — not every skill needs to be in every location).

### Cache Architecture

```
~/.claude/plugins/
├── installed_plugins.json      ← tracks cached SHA per plugin
├── cache/                      ← snapshots Claude Code reads
│   ├── chalktalk/chalktalk/1.0.0/skills/
│   ├── marbaji-claude/marbaji-claude/{hash}/skills/
│   ├── private-claude/private-claude/{hash}/skills/
│   ├── claude-plugins-official/superpowers/{version}/skills/
│   └── ...
└── marketplaces/               ← live git clones (actual files)
    ├── chalktalk/skills/skills/
    ├── marbaji-claude/skills/
    ├── private-claude/skills/
    └── ...
```

**Key insight:** When you develop skills locally (edit marketplace clone, push to GitHub), the cache does NOT update. You must manually sync the cache or the skill list will show stale/missing/renamed skills.

## Locations to Scan

### GitHub Repos → Marketplace Clones

| GitHub Repo (remote) | Marketplace Clone (local) | Skills subdirectory |
|---|---|---|
| `ChalkTalk/claude` | `~/.claude/plugins/marketplaces/chalktalk` | `skills/skills/` |
| `marbaji/marbaji-claude` | `~/.claude/plugins/marketplaces/marbaji-claude` | `skills/` |
| `marbaji/private-claude` | `~/.claude/plugins/marketplaces/private-claude` | `skills/` |

### Desktop Folders

| Folder | Should contain |
|---|---|
| `~/Desktop/Claude Code/Skills/chalktalk/` | Symlinks → chalktalk marketplace clone |
| `~/Desktop/Claude Code/Skills/marbaji/` | Symlinks → marbaji marketplace clone |
| `~/Desktop/Claude Code/Skills/private/` | Symlinks → private-claude marketplace clone |

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

# Marketplace clone: marbaji/private-claude
PRIVATE_CLONE="$HOME/.claude/plugins/marketplaces/private-claude/skills"
echo "=== marbaji/private-claude clone ===" && ls "$PRIVATE_CLONE" 2>/dev/null

# Desktop/chalktalk
DESK_CT="$HOME/Desktop/Claude Code/Skills/chalktalk"
echo "=== Desktop/chalktalk ===" && ls "$DESK_CT" 2>/dev/null

# Desktop/marbaji
DESK_MA="$HOME/Desktop/Claude Code/Skills/marbaji"
echo "=== Desktop/marbaji ===" && ls "$DESK_MA" 2>/dev/null

# Desktop/private
DESK_PR="$HOME/Desktop/Claude Code/Skills/private"
echo "=== Desktop/private ===" && ls "$DESK_PR" 2>/dev/null

# ~/.claude/skills
echo "=== ~/.claude/skills ===" && ls ~/.claude/skills/ 2>/dev/null
```

### Step 2: Check GitHub sync status

For each marketplace clone, check if it's up to date with GitHub:

```bash
cd ~/.claude/plugins/marketplaces/chalktalk && git fetch --dry-run 2>&1
cd ~/.claude/plugins/marketplaces/marbaji-claude && git fetch --dry-run 2>&1
cd ~/.claude/plugins/marketplaces/private-claude && git fetch --dry-run 2>&1
```

If `git fetch --dry-run` shows output, the clone is behind GitHub.

### Step 2b: Plugin Cache Staleness Check

Compare the plugin cache (what Claude Code actually reads) against the marketplace clone (the live source files). This catches renamed, added, or deleted skills that the cache doesn't reflect.

#### Plugin-to-Cache Mapping

| Plugin key in installed_plugins.json | Cache path | Marketplace source path |
|---|---|---|
| `chalktalk@chalktalk` | `~/.claude/plugins/cache/chalktalk/chalktalk/1.0.0/skills/` | `~/.claude/plugins/marketplaces/chalktalk/skills/skills/` |
| `marbaji-claude@marbaji-claude` | `~/.claude/plugins/cache/marbaji-claude/marbaji-claude/*/skills/` | `~/.claude/plugins/marketplaces/marbaji-claude/skills/` |
| `private-claude@private-claude` | `~/.claude/plugins/cache/private-claude/private-claude/*/skills/` | `~/.claude/plugins/marketplaces/private-claude/skills/` |

**Note:** Third-party plugins (superpowers, code-review, document-skills, obsidian, etc.) are out of scope — their caches are managed by `claude plugin update`.

#### 2b.1 SHA comparison

```bash
# Read cached SHAs from installed_plugins.json
INSTALLED="$HOME/.claude/plugins/installed_plugins.json"

# For each of our plugins, compare cached SHA vs marketplace HEAD
for repo_info in \
  "chalktalk@chalktalk|$HOME/.claude/plugins/marketplaces/chalktalk" \
  "marbaji-claude@marbaji-claude|$HOME/.claude/plugins/marketplaces/marbaji-claude" \
  "private-claude@private-claude|$HOME/.claude/plugins/marketplaces/private-claude"; do

  key="${repo_info%%|*}"
  clone_path="${repo_info##*|}"

  # Get cached SHA (from installed_plugins.json)
  cached_sha=$(python3 -c "
import json
with open('$INSTALLED') as f:
    data = json.load(f)
entries = data.get('plugins', {}).get('$key', [])
print(entries[0]['gitCommitSha'] if entries else 'NOT_INSTALLED')
")

  # Get marketplace HEAD
  head_sha=$(cd "$clone_path" && git rev-parse HEAD 2>/dev/null || echo "NO_CLONE")

  if [ "$cached_sha" = "$head_sha" ]; then
    echo "$key: ✅ in sync ($cached_sha)"
  else
    echo "$key: ❌ STALE (cache=$cached_sha, source=$head_sha)"
  fi
done
```

#### 2b.2 Skill directory comparison

For each of our two plugins, compare the skill directories in cache vs marketplace:

```bash
# ChalkTalk
echo "=== chalktalk cache vs source ==="
CACHE_CT="$HOME/.claude/plugins/cache/chalktalk/chalktalk/1.0.0/skills"
SOURCE_CT="$HOME/.claude/plugins/marketplaces/chalktalk/skills/skills"
diff <(ls "$CACHE_CT" 2>/dev/null | sort) <(ls "$SOURCE_CT" 2>/dev/null | sort)

# marbaji-claude (cache path uses a hash — find it)
echo "=== marbaji-claude cache vs source ==="
CACHE_MA=$(find "$HOME/.claude/plugins/cache/marbaji-claude" -maxdepth 3 -name "skills" -type d 2>/dev/null | head -1)
SOURCE_MA="$HOME/.claude/plugins/marketplaces/marbaji-claude/skills"
diff <(ls "$CACHE_MA" 2>/dev/null | sort) <(ls "$SOURCE_MA" 2>/dev/null | sort)

# private-claude (cache path uses a hash — find it)
echo "=== private-claude cache vs source ==="
CACHE_PR=$(find "$HOME/.claude/plugins/cache/private-claude" -maxdepth 3 -name "skills" -type d 2>/dev/null | head -1)
SOURCE_PR="$HOME/.claude/plugins/marketplaces/private-claude/skills"
diff <(ls "$CACHE_PR" 2>/dev/null | sort) <(ls "$SOURCE_PR" 2>/dev/null | sort)
```

If `diff` produces output, the cache is out of sync. Lines starting with `<` are in cache but not source (deleted/renamed skills). Lines starting with `>` are in source but not cache (new skills).

#### 2b.3 Add cache column to the comparison table

Add a **Cache** column to the Step 4 table:

```
| Skill | GitHub | Clone | Cache | Desktop | ~/.claude/skills |
```

Cache column values:
- `✅ cached` — skill exists in the plugin cache
- `❌ missing` — skill exists in clone but NOT in cache (Claude Code can't see it)
- `👻 stale` — skill exists in cache but NOT in clone (renamed or deleted — ghost entry)
- empty — skill is from a different plugin (out of scope)

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
| Skill | GitHub | Clone | Cache | Desktop | ~/.claude/skills |
|---|---|---|---|---|---|
```

**Column definitions:**

| Column | What it means | Possible values |
|---|---|---|
| GitHub | Exists in the remote repo on github.com | `✅` or empty |
| Clone | Exists in the local marketplace clone (the real files) | `✅ dir` (always a dir — this is where files live) or empty |
| Cache | Exists in `~/.claude/plugins/cache/` (what Claude Code loads for `/skill` list) | `✅ cached` / `❌ missing` / `👻 stale` / empty |
| Desktop | Entry in `~/Desktop/Claude Code/Skills/` | `✅ symlink` / `✅ dir` / `❌ broken` / empty |
| ~/.claude/skills | Entry in `~/.claude/skills/` (what Claude loads) | `✅ symlink` / `✅ dir` / `❌ broken` / empty |

**Expected healthy state:** GitHub = ✅, Clone = ✅ dir, Cache = ✅ cached, Desktop = ✅ symlink, ~/.claude/skills = ✅ symlink. Any deviation is flagged as an issue.

**Scope:** This inventory only tracks skills from our three repos (`ChalkTalk/claude`, `marbaji/marbaji-claude`, and `marbaji/private-claude`). Third-party skills (superpowers, code-review, document-skills, etc.) are managed by their own marketplace plugins and are out of scope — ignore them.

**Grouping:** Group rows by origin repo:
1. **ChalkTalk skills** — any skill that exists in `ChalkTalk/claude`
2. **Personal skills (public)** — any skill that exists in `marbaji/marbaji-claude`
3. **Private skills** — any skill that exists in `marbaji/private-claude`

When classifying entries in `~/.claude/skills/` and Desktop, skip any entry whose symlink target points outside our three marketplace clones, or any standalone directory that doesn't match a skill name in any of the three repos.

### Step 5: Flag issues

After the table, list any problems found:

- **Cache stale (SHA mismatch)** — `installed_plugins.json` SHA doesn't match marketplace HEAD. Skills in the cache may be outdated, renamed, or missing. **This is the most impactful issue** — it means Claude Code's `/skill` list is wrong.
- **Missing from cache** — skill exists in the marketplace clone but not in the plugin cache. Claude Code can't see it. Shows as `❌ missing` in Cache column.
- **Ghost in cache** — skill exists in the cache but not in the marketplace clone. It was renamed or deleted but the cache still has the old version. Shows as `👻 stale` in Cache column.
- **Broken symlinks** — point to paths that don't exist (shows as `❌ broken`)
- **Missing from Desktop** — in Clone but no Desktop entry
- **Missing from ~/.claude/skills** — in Clone but Claude Code can't load it
- **Standalone copies (`dir`)** — directories in Desktop or ~/.claude/skills that should be symlinks. These won't auto-update when you `git pull` the clone.
- **Clone behind GitHub** — `git fetch --dry-run` showed pending changes

### Step 6: Offer fixes

For each issue found, offer a concrete fix command:

- **Cache stale / missing / ghost** → Sync the cache from the marketplace clone:
  ```bash
  # For chalktalk:
  rm -rf ~/.claude/plugins/cache/chalktalk/chalktalk/1.0.0/skills/
  cp -r ~/.claude/plugins/marketplaces/chalktalk/skills/skills/ \
        ~/.claude/plugins/cache/chalktalk/chalktalk/1.0.0/skills/

  # For marbaji-claude (find the cache hash first):
  CACHE_MA=$(find ~/.claude/plugins/cache/marbaji-claude -maxdepth 2 -type d -name "skills" | head -1 | sed 's|/skills$||')
  rm -rf "$CACHE_MA/skills/"
  cp -r ~/.claude/plugins/marketplaces/marbaji-claude/skills/ "$CACHE_MA/skills/"

  # For private-claude (find the cache hash first):
  CACHE_PR=$(find ~/.claude/plugins/cache/private-claude -maxdepth 2 -type d -name "skills" | head -1 | sed 's|/skills$||')
  rm -rf "$CACHE_PR/skills/"
  cp -r ~/.claude/plugins/marketplaces/private-claude/skills/ "$CACHE_PR/skills/"
  ```
  Then update `installed_plugins.json` with the current HEAD SHA:
  ```bash
  # Get current HEAD for the plugin's marketplace clone
  NEW_SHA=$(cd <clone-path> && git rev-parse HEAD)
  # Edit installed_plugins.json: update gitCommitSha and lastUpdated for the plugin
  ```
  **Requires Claude Code restart** for the skill list to refresh.

- Broken symlink → `rm <broken> && ln -s <clone-path> <name>`
- Missing from Desktop → `ln -s <clone-path> "<desktop-path>/<name>"`
- Missing from ~/.claude/skills → `ln -s <clone-path> ~/.claude/skills/<name>`
- Standalone copy that should be a symlink → `rm -rf <dir> && ln -s <clone-path> <name>` (confirm with user first — standalone copies may have local changes)
- Clone behind GitHub → `cd <clone-path> && git pull`

Present all fixes and ask the user which ones to apply. Do not auto-apply destructive fixes (removing directories).

**After fixing caches:** Always remind the user to restart Claude Code for cache changes to take effect.
