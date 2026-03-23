---
name: inventory-checker
description: Display a complete inventory of all installed Claude Code components including MCP servers (with status), plugin marketplaces, available skills, npm packages, Python packages, Homebrew packages, and key CLI tools. Use this when the user asks what they have installed, what's configured, or wants to see their complete Claude Code setup.
---

# Claude Code Inventory Checker

This skill provides a comprehensive overview of all installed Claude Code components.

## What This Skill Does

When triggered, this skill will:
1. List all MCP servers with their connection status
2. Show configured plugin marketplaces
3. Display all available skills from installed marketplaces
4. List global npm packages
5. List Python packages (pip3)
6. List Homebrew packages
7. Check key CLI tools in PATH
8. Provide summary statistics

## Instructions

When the user asks about their installed components, setup, or configuration, run the following commands to generate a complete inventory:

### Step 1: List MCP Servers
```bash
claude mcp list
```

This shows all MCP servers with their status (connected, needs authentication, or failed).

### Step 2: List Plugin Marketplaces
```bash
claude plugin marketplace list
```

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

### Step 7: Check Key CLI Tools

Instead of checking a hardcoded list, derive CLI tools from what's actually installed. Run this to find all globally-installed binaries that are in PATH:

```bash
# Get bin names from npm global packages
npm list -g --depth=0 --parseable 2>/dev/null | tail -n +2 | while read pkg; do
  ls "$pkg/bin" 2>/dev/null
done | sort -u

# Also check these core tools that don't come from package managers
for cmd in python3 node npm npx git gh claude obsidian; do
  which "$cmd" 2>/dev/null
done
```

This way new tools (like `gws` from `@googleworkspace/cli`) are automatically picked up without needing to update the skill.

### Step 8: Format the Output

Organize the results into clear sections:

**MCP Servers** - Categorize by status AND source:
- Split into **Local** (added via `claude mcp add`, run on your machine) and **Cloud** (connected via claude.ai/settings/connectors, prefixed with `claude.ai` in the list, run on Anthropic's servers)
- Within each group, categorize by status:
  - ✅ Working & Connected
  - ⚠️ Needs Authentication
  - ❌ Connection Failed

**Plugin Marketplaces** - List with source information

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

**Key CLI Tools in PATH** - Verify essential tools are accessible

**Summary Stats** - Count of each category

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
- Group similar items together for clarity
- Use emoji indicators for status (✅ ⚠️ ❌)
- Categorize Python packages by their purpose (AI/ML, document processing, web, utilities)
- Group Homebrew packages by type (dev tools, media, system libraries)
- Show versions where available for npm and Python packages
- Verify that key CLI tools are in PATH and accessible
- Provide counts/statistics at the end for all categories
- If a command fails, note it and continue with other checks
- Offer to help fix issues if any are found
- Run all checks in parallel where possible for efficiency
