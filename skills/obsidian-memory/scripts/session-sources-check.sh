#!/bin/bash
# session-sources-check.sh — the session-end gate for Sources/ notes.
#
# Lists every external source this session touched (documents used, artifacts published,
# canonical sources fetched: URLs, Drive files, Gmail attachments) and checks that each
# one is named in a Sources/ note written or edited since the session started.
# Exit 1 with the uncovered list means the ritual may not close until each item has a
# note or an explicit skip from the user. Exit 0 prints the covered count, never silence.
# Exit 2 is a setup failure (no transcript, no vault) and is NOT a pass.
#
# Usage: session-sources-check.sh [SESSION_JSONL] [VAULT_PATH]
#   SESSION_JSONL defaults to the transcript named by $CLAUDE_CODE_SESSION_ID (the Bash tool
#   exports it), falling back to the newest transcript for the current working directory.
#   VAULT_PATH defaults to $OBSIDIAN_VAULT_PATH or "~/Documents/Claude Code Obsidian".
# Env: SOURCES_CHECK_SINCE=<epoch> overrides the session-start timestamp (for tests).
set -u
JSONL="${1:-}"
if [ -z "$JSONL" ] && [ -n "${CLAUDE_CODE_SESSION_ID:-}" ]; then
  JSONL="$(ls "$HOME"/.claude/projects/*/"$CLAUDE_CODE_SESSION_ID".jsonl 2>/dev/null | head -1)"
fi
if [ -z "$JSONL" ]; then
  PROJ_DIR="$HOME/.claude/projects/$(pwd | sed 's#[^A-Za-z0-9]#-#g')"
  JSONL="$(ls -t "$PROJ_DIR"/*.jsonl 2>/dev/null | head -1)"
fi
VAULT="${2:-${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Claude Code Obsidian}}"
[ -n "$JSONL" ] && [ -f "$JSONL" ] || { echo "sources-check: SETUP FAILURE, no transcript found (session id: ${CLAUDE_CODE_SESSION_ID:-unset}, cwd: $(pwd))"; exit 2; }
[ -d "$VAULT/Sources" ] || { echo "sources-check: SETUP FAILURE, no Sources/ folder at $VAULT"; exit 2; }
exec python3 - "$JSONL" "$VAULT" <<'PY'
import json, os, re, sys, glob, time, calendar
jsonl, vault = sys.argv[1], sys.argv[2]
home = os.path.expanduser("~")
scratch_re = re.compile(r"^/private/tmp/claude-|^/tmp/")
vault_re = re.compile("^" + re.escape(vault))
repos_re = re.compile("^" + re.escape(home) + r"/Desktop/Claude Code/30-repos/")
office_ext = r"pdf|xlsx?|csv|docx?|pptx?"            # documents count anywhere under a watch root
loose_ext = r"md|json|txt|html"                        # notes/data count only outside the workspace
path_re = re.compile(r"((?:/Users/|~/)[^\n\"'`]*?\.(?:" + office_ext + "|" + loose_ext + r"))(?=$|[\s\"'`;|&)>,])", re.I)
watch_roots = [home + "/Downloads/", home + "/Desktop/", home + "/Documents/"]
workspace = home + "/Desktop/Claude Code/"
items = {}  # token -> description
def add(tok, desc):
    if tok and tok not in items: items[tok] = desc
def path_item(p):
    p = os.path.expanduser(p.strip())
    if scratch_re.search(p) or vault_re.search(p) or repos_re.search(p): return
    if "/Screenshot " in p or "/.claude/" in p: return
    if not any(p.startswith(r) for r in watch_roots): return
    if re.search(r"/(spec|plan|handoff)_[^/]*\.md$", p): return  # actionables have their own closing step
    if p.startswith(workspace) and not re.search(r"\.(" + office_ext + r")$", p, re.I): return  # workspace .md/.json/.html are our own
    add(os.path.basename(p), "file used: " + p)
def paths_in(text):
    for p in path_re.findall(text): path_item(p)
def utc(ts):
    try: return calendar.timegm(time.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception: return None
started = None
for line in open(jsonl, errors="replace"):
    try: o = json.loads(line)
    except Exception: continue
    if started is None and o.get("timestamp"): started = utc(o["timestamp"])
    m = o.get("message")
    if not isinstance(m, dict): continue
    content = m.get("content")
    if isinstance(content, str):
        if o.get("type") == "user":
            for u in re.findall(r"https?://[^\s)\]>\"']+", content): add(u.rstrip(".,"), "user-shared URL")
            paths_in(content)
        continue
    for blk in content or []:
        if not isinstance(blk, dict): continue
        if blk.get("type") == "text" and o.get("type") == "user" and not blk.get("text", "").startswith("Base directory for this skill"):
            for u in re.findall(r"https?://[^\s)\]>\"']+", blk.get("text", "")): add(u.rstrip(".,"), "user-shared URL")
            paths_in(blk.get("text", ""))
        if blk.get("type") != "tool_use": continue
        n, inp = blk.get("name", ""), blk.get("input") or {}
        if n in ("Read", "Write", "Edit"): path_item(inp.get("file_path", ""))
        elif n == "Bash":
            cmd = inp.get("command", "")
            paths_in(cmd)
            for fid in re.findall(r"\"fileId\"\s*:\s*\"([A-Za-z0-9_-]{15,})\"", cmd): add(fid, "Google Drive file (gws)")
            for mid in re.findall(r"\"messageId\"\s*:\s*\"([0-9a-f]{12,})\"", cmd): add(mid, "Gmail message attachment (gws)")
            if "gws " in cmd:  # ids passed as bare args to a helper, e.g. dl <fileId> out.pdf / att <messageId> <attId> out.pdf
                for tok in re.findall(r"(?<![A-Za-z0-9_/.-])(1[A-Za-z0-9_-]{24,59}|0B[A-Za-z0-9_-]{23,59})(?![A-Za-z0-9_/.-])", cmd): add(tok, "Google Drive file (gws helper arg)")
                for tok in re.findall(r"(?<![A-Za-z0-9_/.-])([0-9a-f]{16})(?![A-Za-z0-9_/.-])", cmd): add(tok, "Gmail message (gws helper arg)")
        elif n == "mcp__claude_ai_Google_Drive__read_file_content": add(inp.get("fileId"), "Google Drive file (MCP)")
        elif n == "WebFetch" or n.startswith("mcp__firecrawl") or n.startswith("firecrawl"):
            add(inp.get("url") or inp.get("query"), "fetched URL")
        elif n.startswith("mcp__playwright__browser_navigate") or n == "mcp__claude-in-chrome__navigate":
            u = inp.get("url", "")
            if u.startswith("http") and "claude.ai" not in u: add(u, "visited URL")
# artifacts published this session: ledger rows {date, title, url, account, cwd, source} from the artifact-source hook
led = os.path.expanduser("~/.claude/state/artifacts.jsonl")
if os.path.exists(led) and started:
    for line in open(led, errors="replace"):
        try: r = json.loads(line)
        except Exception: continue
        rt = utc(r.get("date") or r.get("ts") or r.get("timestamp") or "")
        if rt and rt >= started - 60: add(r.get("url"), "artifact published: " + str(r.get("title") or r.get("source") or ""))
since = float(os.environ.get("SOURCES_CHECK_SINCE", started or 0))
notes = [f for f in glob.glob(os.path.join(vault, "Sources", "*.md")) if os.path.getmtime(f) >= since - 60]
text = "\n".join(open(f, errors="replace").read() for f in notes)
def named(tok):
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(tok) + r"(?![A-Za-z0-9])", text) is not None
if not items:
    print("sources-check: 0 sources touched this session; nothing to log."); sys.exit(0)
missing = [(t, d) for t, d in items.items() if not named(t)]
covered = len(items) - len(missing)
print(f"sources-check: {len(items)} source(s) touched, {covered} covered by {len(notes)} Sources note(s) written this session.")
if missing:
    print("UNCOVERED (write a Sources/ note naming each, or get an explicit skip from the user):")
    for t, d in missing: print(f"  - {t}    [{d}]")
    sys.exit(1)
PY
