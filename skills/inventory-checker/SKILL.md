---
name: inventory-checker
description: Display a complete inventory of all installed Claude Code components including MCP servers (with status), plugin marketplaces, available skills, npm packages, Python packages, Homebrew packages, and key CLI tools. Use this when the user asks what they have installed, what's configured, or wants to see their complete Claude Code setup.
---

# Claude Code Inventory Checker

This skill provides a comprehensive overview of all installed Claude Code components.

## What This Skill Does

When triggered, this skill will:
1. List all MCP servers with their connection status (local AND cloud)
2. Show configured plugin marketplaces (and flag stale caches)
3. Display all available skills from installed marketplaces
4. List global npm packages
5. List Python packages (pip3)
6. List Homebrew packages
7. Discover all CLI tools in PATH dynamically
8. Provide summary statistics and flag issues

## Instructions

When the user asks about their installed components, setup, or configuration, run the following commands to generate a complete inventory:

### Step 1: List MCP Servers

Run both commands — `claude mcp list` may not show cloud connectors in all environments (e.g. Claude Desktop's Code tab doesn't surface them). The second command catches what the first misses.

```bash
claude mcp list
```

Then also check which cloud connectors are actually available in this session by looking at tool prefixes. This works in both CLI and Desktop:

```bash
# List available MCP tool prefixes to detect cloud connectors
# Look at the system-reminder in context for tools starting with mcp__claude_ai_
# Each unique mcp__claude_ai_<ServiceName>__ prefix = one cloud connector
```

To do this: scan the available tools in your current context for any that start with `mcp__claude_ai_`. Extract the unique service names (e.g. `mcp__claude_ai_Slack__` → Slack). These are cloud connectors that are active in this session, even if `claude mcp list` didn't show them.

**Combine both sources.** If `claude mcp list` shows `claude.ai Slack` AND you see `mcp__claude_ai_Slack__` tools, that's one server (not two). If `claude mcp list` misses it but the tools exist, it's still connected.

### Step 2: List Plugin Marketplaces

```bash
claude plugin marketplace list
```

### Step 2b: Detect Stale Marketplace Caches

Check for marketplace directories on disk that are no longer in the active marketplace list:

```bash
# List marketplace dirs on disk
ls ~/.claude/plugins/marketplaces/ 2>/dev/null | sort

# List cache dirs on disk
ls ~/.claude/plugins/cache/ 2>/dev/null | sort
```

Compare these against the output of `claude plugin marketplace list`. Any directory that exists on disk but is NOT in the active list is a stale cache. Flag these for cleanup.

### Step 3: List All Available Skills (grouped by marketplace)
```bash
find ~/.claude/plugins ~/.claude/skills -name "SKILL.md" 2>/dev/null | python3 -c "
import sys, re
from collections import defaultdict
groups = defaultdict(set)
for line in sys.stdin:
    p = line.strip()
    m = re.search(r'\.claude/skills/([^/]+)/SKILL\.md', p)
    if m:
        groups['local'].add(m.group(1))
        continue
    m = re.search(r'plugins/cache/([^/]+)/[^/]+/[^/]+/skills/([^/]+)/SKILL\.md', p)
    if m:
        groups[m.group(1)].add(m.group(2))
        continue
    m = re.search(r'plugins/marketplaces/([^/]+)/.+/([^/]+)/SKILL\.md', p)
    if m:
        groups[m.group(1)].add(m.group(2))
        continue
for mkt, skills in sorted(groups.items()):
    print(f'\n{mkt} ({len(skills)}):')
    for s in sorted(skills):
        print(f'  {s}')
"
```

This groups skills by their source marketplace so you can see what came from where. Skills under `local` are manually placed in `~/.claude/skills/`.

**Important:** If the same skill names appear under multiple marketplaces (e.g. `brainstorming` under both `claude-plugins-official` and `superpowers-marketplace`), this does NOT mean they are loaded twice. The `find` command searches the plugin cache on disk, which contains all files from every installed marketplace — but only **enabled** plugins actually load at runtime. Call out any duplicates you see and explain that they are cached copies, not runtime duplicates.

### Step 4: List Global npm Packages
```bash
npm list -g --depth=0 2>/dev/null
```

### Step 5: List Python Packages
```bash
pip3 list 2>/dev/null | { head -30; echo ""; } && echo "Total packages: $(pip3 list 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')"
```

### Step 6: List Homebrew Packages
```bash
brew list 2>/dev/null | { head -30; echo ""; } && echo "Total packages: $(brew list 2>/dev/null | wc -l | tr -d ' ')"
```

### Step 7: Discover CLI Tools in PATH

Discover all CLI tools dynamically from package managers — don't use a hardcoded list.

```bash
# 1. Binaries from npm global packages
npm list -g --depth=0 --parseable 2>/dev/null | tail -n +2 | while read pkg; do
  ls "$pkg/bin" 2>/dev/null
done | sort -u

# 2. Verify system essentials that don't come from package managers
for cmd in python3 node git gh claude obsidian; do
  which "$cmd" 2>/dev/null
done
```

This picks up tools like `gws`, `firecrawl`, `npx` automatically from npm. No hardcoded lists to maintain.

### Step 8: Format the Output

Organize the results into clear sections:

**MCP Servers** - Categorize by status AND source:
- Split into **Local** (added via `claude mcp add`, run on your machine) and **Cloud** (connected via claude.ai/settings/connectors, prefixed with `claude.ai` in the list or detected via `mcp__claude_ai_*` tool prefixes)
- Identify **duplicates** where the same service has both a cloud connector and a local MCP (e.g. Atlassian, Supernova). Note this — it's not a problem, the local one works alongside the cloud one.
- Within each group, categorize by status:
  - ✅ Working & Connected
  - ⚠️ Needs Authentication
  - ❌ Connection Failed

**Plugin Marketplaces** - List with source information. Flag any stale caches found in Step 2b.

**Skills Available** - Display grouped by marketplace as returned by the command. Show the marketplace name as the section header with skill count, then list skills under it.

**Python Packages** - Categorize by purpose:
- AI & Machine Learning
- Document Processing
- Web & API
- Utilities

**npm Global Packages** - List with versions

**Homebrew Packages** - Group by category:
- Development Tools
- Media & Image Processing
- System Libraries
- Utilities

**CLI Tools in PATH** - All discovered tools with their full paths

**Summary Stats** - Count of each category

**Issues Found** - List any problems detected:
- Failed MCP connections
- Stale marketplace caches
- Cloud+local duplicates (informational, not an error)
- Missing expected tools

## Examples

User requests that trigger this skill:
- "What do I have installed?"
- "Show me my Claude Code setup"
- "What MCPs are configured?"
- "List all my skills and plugins"
- "I lost track of what I've installed, can you show me?"
- "What's my complete Claude Code inventory?"

## Guidelines

- Always show connection status for MCP servers
- Detect cloud connectors via BOTH `claude mcp list` AND available tool prefixes
- Group similar items together for clarity
- Use emoji indicators for status (✅ ⚠️ ❌)
- Categorize Python packages by their purpose (AI/ML, document processing, web, utilities)
- Group Homebrew packages by type (dev tools, media, system libraries)
- Show versions where available for npm and Python packages
- Discover CLI tools dynamically from package managers — never hardcode a list
- Provide counts/statistics at the end for all categories
- Flag stale caches, failed connections, and duplicates in an Issues section
- If a command fails, note it and continue with other checks
- Offer to help fix issues if any are found
- Run all checks in parallel where possible for efficiency
