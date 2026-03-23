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

You MUST do BOTH Step 1a and Step 1b. `claude mcp list` alone misses cloud connectors — especially in Claude Code Desktop.

**Step 1a — Local/configured MCP servers:**
```bash
claude mcp list
```

**Step 1b — Cloud connectors (REQUIRED, do NOT skip):**

Cloud connectors from claude.ai/settings/connectors are injected into the runtime tool registry but are often invisible to `claude mcp list` in Claude Code Desktop. They appear as **deferred tools** listed in `<system-reminder>` messages at the top of the conversation.

To detect them:

1. Look at the deferred tools list in the system-reminder messages in your conversation context
2. Extract all tool names that start with `mcp__`
3. Group by server prefix — the segment between the first and second `__` (e.g., `mcp__33d58cf5-37c2-447c-b3de-20aa72bdad7e__gmail_search_messages` → server ID is `33d58cf5-37c2-447c-b3de-20aa72bdad7e`)
4. **UUID-prefixed servers** (e.g., `mcp__33d58cf5-...`) are cloud connectors NOT shown by `claude mcp list`
5. **Named servers** (e.g., `mcp__slack__`, `mcp__github__`) are local MCP servers already covered by Step 1a

To identify which service each UUID-prefixed server represents, look at its tool names:

| Tool name patterns | Service |
|--------------------|---------|
| `gmail_*` | Gmail |
| `gcal_*` | Google Calendar |
| `google_drive_*` | Google Drive |
| `notion-*`, `notion_*` | Notion |
| `get_crm_objects`, `search_crm_objects`, `get_properties` | HubSpot CRM |
| `search_contacts`, `get_conversation`, `list_articles` | Intercom |
| `ramp_*`, `load_spend_*`, `load_cards`, `load_users` | Ramp |
| `execute_workflow`, `search_workflows`, `publish_workflow` | n8n Workflows |
| `generate-design`, `export-design`, `search-designs` | Canva |
| `list_files`, `read_file`, `run_query` (when UUID-prefixed) | Google Sheets |

You can also confirm via ToolSearch if needed:
```
ToolSearch(query="+mcp__ gmail", max_results=5)
```

**Combine both sources.** Deduplicate: if `claude mcp list` shows `slack` AND the deferred tools list has `mcp__slack__*` tools, that's one server, not two. The total MCP count = unique servers from both sources combined.

**Exclude built-in platform servers** from the count — these are part of Claude Code itself, not user-configured. Mention them in a footnote but don't include in MCP totals:
- `mcp__Claude_Preview__*` — Claude Preview
- `mcp__Claude_in_Chrome__*` — Claude in Chrome
- `mcp__scheduled-tasks__*` — Scheduled Tasks
- `mcp__mcp-registry__*` — MCP Registry

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

Compare these against the output of `claude plugin marketplace list`:
- Any directory in `marketplaces/` or `cache/` that is NOT in the active marketplace list is a **stale cache**. Flag these for cleanup.
- **Not all marketplaces have a separate cache directory.** Some marketplaces store their plugin data directly in the `marketplaces/` directory (with a nested plugin folder inside) and never create a `cache/` entry. A marketplace appearing in `marketplaces/` but missing from `cache/` is **normal** — do NOT flag this as an issue. Only flag directories that exist on disk but are absent from the active `claude plugin marketplace list` output.

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

**MCP Servers** — Use standard markdown tables. Split into two sections:

1. **Local servers** — added via `claude mcp add`, run on user's machine
2. **Cloud — claude.ai connectors** — detected as UUID-prefixed servers in the deferred tools list

Each table has three columns: Server, Purpose, Status.

Example format:

```markdown
### MCP Servers (N total — X connected, Y failed)

**Local (N servers)**

| Server | Purpose | Status |
|---|---|---|
| slack | Team messaging | ✅ Connected |
| github | Repos, PRs, issues | ✅ Connected |

**Cloud — claude.ai connectors (N servers)**

| Server | Purpose | Status |
|---|---|---|
| claude.ai Gmail | Email read/draft | ✅ Connected |
| claude.ai Google Calendar | Calendar & scheduling | ✅ Connected |

> Built-in platform servers excluded: Claude Preview, Claude in Chrome, Scheduled Tasks, MCP Registry
> Duplicates (cloud + local): Atlassian — both work alongside each other, not a problem.
> Failover: claude.ai Slack failed, but local slack MCP is connected as fallback.
```

Rules for the MCP tables:
- Prefix cloud connector names with `claude.ai` (e.g., `claude.ai Gmail`, `claude.ai Notion`)
- Use status emoji: ✅ Connected, ⚠️ Needs Auth, ❌ Failed
- Add a summary header line: `MCP Servers (N total — X connected, Y failed)`
- After both tables, add blockquote (`>`) notes for:
  - **Duplicates**: services that appear in both local and cloud (informational, not an error)
  - **Failover**: if a cloud connector failed but the local version works, call it out
- Exclude built-in platform servers (Claude Preview, Claude in Chrome, Scheduled Tasks, MCP Registry) from tables — mention in a footnote if desired
- Add a "Purpose" description for each server based on its tool names

**Plugin Marketplaces** - List with source information. Flag any truly stale caches found in Step 2b (directories not in the active list). Do NOT flag marketplaces that simply lack a `cache/` entry — this is normal for marketplaces that store plugins directly in `marketplaces/`.

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
- Stale marketplace caches (directories on disk NOT in the active marketplace list — not simply missing from `cache/`)
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

- Always render MCP servers in standard markdown tables with Server/Purpose/Status columns
- Split MCP into two tables: Local servers and Cloud connectors (prefix cloud names with `claude.ai`)
- Detect cloud connectors via BOTH `claude mcp list` AND UUID-prefixed deferred tools in system-reminder context
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
