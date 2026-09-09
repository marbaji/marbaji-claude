#!/bin/bash
# session-sources-check.sh — the session-end gate for Sources/ notes.
#
# Lists every external source this session touched (files used, artifacts published,
# canonical sources fetched: URLs, Drive files, Gmail attachments) and checks that each
# one is named in a Sources/ note written or edited since the session started.
# Exit 1 with the uncovered list means the ritual may not close until each item has a
# note or an explicit skip from the user. Exit 0 prints the covered count, never silence.
#
# Usage: session-sources-check.sh [SESSION_JSONL] [VAULT_PATH]
#   SESSION_JSONL defaults to the newest transcript for the current working directory.
#   VAULT_PATH defaults to $OBSIDIAN_VAULT_PATH or "~/Documents/Claude Code Obsidian".
# Env: SOURCES_CHECK_SINCE=<epoch> overrides the session-start timestamp (for tests).
set -u
PROJ_DIR="$HOME/.claude/projects/$(pwd | sed 's#[/ ]#-#g')"
JSONL="${1:-$(ls -t "$PROJ_DIR"/*.jsonl 2>/dev/null | head -1)}"
VAULT="${2:-${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Claude Code Obsidian}}"
[ -f "$JSONL" ] || { echo "sources-check: no transcript found (looked in $PROJ_DIR)"; exit 2; }
[ -d "$VAULT/Sources" ] || { echo "sources-check: no Sources/ folder at $VAULT"; exit 2; }
exec python3 - "$JSONL" "$VAULT" <<'PY'
import json, os, re, sys, glob, time
jsonl, vault = sys.argv[1], sys.argv[2]
home = os.path.expanduser("~")
scratch_re = re.compile(r"^/private/tmp/claude-|^/tmp/")
vault_re = re.compile("^" + re.escape(vault))
repos_re = re.compile("^" + re.escape(home) + r"/Desktop/Claude Code/30-repos/")
doc_ext = re.compile(r"\.(pdf|xlsx?|csv|docx?|pptx?|txt|json|md|html)$", re.I)
watch_roots = [home + "/Downloads/", home + "/Desktop/", home + "/Documents/"]
items = {}  # token -> description
def add(tok, desc):
    if tok and tok not in items: items[tok] = desc
def path_item(p):
    p = os.path.expanduser(p)
    if not p.startswith("/") or scratch_re.search(p) or vault_re.search(p) or repos_re.search(p): return
    if "/Screenshot " in p or "/.claude/" in p: return
    if not any(p.startswith(r) for r in watch_roots): return
    if not doc_ext.search(p): return
    if re.search(r"/(spec|plan|handoff)_", p): return  # actionables have their own closing step
    add(os.path.basename(p), "file used: " + p)
started = None
for line in open(jsonl, errors="replace"):
    try: o = json.loads(line)
    except Exception: continue
    ts = o.get("timestamp")
    if ts and started is None:
        try: started = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
        except Exception: pass
    m = o.get("message")
    if not isinstance(m, dict): continue
    content = m.get("content")
    if isinstance(content, str) and o.get("type") == "user":
        for u in re.findall(r"https?://[^\s)\]>\"']+", content): add(u.rstrip(".,"), "user-shared URL")
        for p in re.findall(r"(/Users/[^\s\"']+)", content): path_item(p)
        continue
    for blk in content or []:
        if not isinstance(blk, dict): continue
        if blk.get("type") == "text" and o.get("type") == "user" and not blk.get("text", "").startswith("Base directory for this skill"):
            for u in re.findall(r"https?://[^\s)\]>\"']+", blk.get("text", "")): add(u.rstrip(".,"), "user-shared URL")
            for p in re.findall(r"(/Users/[^\s\"']+)", blk.get("text", "")): path_item(p)
        if blk.get("type") != "tool_use": continue
        n, inp = blk.get("name", ""), blk.get("input") or {}
        if n in ("Read", "Write", "Edit"): path_item(inp.get("file_path", ""))
        elif n == "Bash":
            cmd = inp.get("command", "")
            for p in re.findall(r"(/Users/[^\s\"'`;|&)]+|~/[^\s\"'`;|&)]+)", cmd): path_item(p)
            for fid in re.findall(r"\"fileId\"\s*:\s*\"([A-Za-z0-9_-]{15,})\"", cmd): add(fid, "Google Drive file (gws)")
            for mid in re.findall(r"\"messageId\"\s*:\s*\"([0-9a-f]{12,})\"", cmd): add(mid, "Gmail message attachment (gws)")
            if "gws " in cmd:  # ids passed as bare args to a helper function, e.g. dl <fileId> out.pdf / att <messageId> <attId> out.pdf
                for tok in re.findall(r"(?<![A-Za-z0-9_/.-])([A-Za-z0-9_-]{25,60})(?![A-Za-z0-9_/.-])", cmd):
                    if not tok.startswith("ANGjdJ") and "-" not in tok[:1]: add(tok, "Google Drive file (gws helper arg)")
                for tok in re.findall(r"(?<![A-Za-z0-9_/.-])([0-9a-f]{16})(?![A-Za-z0-9_/.-])", cmd): add(tok, "Gmail message (gws helper arg)")
        elif n == "mcp__claude_ai_Google_Drive__read_file_content": add(inp.get("fileId"), "Google Drive file (MCP)")
        elif n in ("WebFetch",) or n.startswith("mcp__firecrawl") or n.startswith("firecrawl"):
            add(inp.get("url") or inp.get("query"), "fetched URL")
        elif n.startswith("mcp__playwright__browser_navigate") or n == "mcp__claude-in-chrome__navigate":
            u = inp.get("url", "")
            if u.startswith("http") and "claude.ai" not in u: add(u, "visited URL")
# artifacts published this session (ledger written by the artifact-source hook)
led = os.path.expanduser("~/.claude/state/artifacts.jsonl")
if os.path.exists(led) and started:
    for line in open(led, errors="replace"):
        try: r = json.loads(line)
        except Exception: continue
        t = r.get("ts") or r.get("timestamp") or ""
        try: rt = time.mktime(time.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
        except Exception: rt = None
        if rt and rt >= started - 60:
            add(r.get("url") or r.get("artifact_url"), "artifact published: " + str(r.get("file") or r.get("file_path") or ""))
since = float(os.environ.get("SOURCES_CHECK_SINCE", started or 0))
notes = [f for f in glob.glob(os.path.join(vault, "Sources", "*.md")) if os.path.getmtime(f) >= since - 60]
text = "\n".join(open(f, errors="replace").read() for f in notes)
if not items:
    print("sources-check: 0 sources touched this session; nothing to log."); sys.exit(0)
missing = [(t, d) for t, d in items.items() if t not in text]
covered = len(items) - len(missing)
print(f"sources-check: {len(items)} source(s) touched, {covered} covered by {len(notes)} Sources note(s) written this session.")
if missing:
    print("UNCOVERED (write a Sources/ note naming each, or get an explicit skip from the user):")
    for t, d in missing: print(f"  - {t}    [{d}]")
    sys.exit(1)
PY
