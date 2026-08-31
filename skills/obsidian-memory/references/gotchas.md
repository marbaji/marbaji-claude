# Gotchas

Failure points accumulated from real runs of the `obsidian-memory` skill. Add an entry every time the skill hits a surprising failure — wrong CLI subcommand, vault path confusion, missing approval step, etc.

---

## `next_steps` and `status` REPLACE the section, they do not append

`ProjectDocUpdate.next_steps` and `.status` overwrite the entire body of their section verbatim. The schema says so, but it reads like an update field and behaves like a truncate.

**The failure:** a session-end for one workstream wrote next steps for that workstream only, silently deleting three live items belonging to a different thread of the same project (2026-08-30, InBloom: permit occupancy, ZR 24-11 lot area and a website sidecar re-pull all vanished). It was caught only because the helper's change report prints removed lines with `-` markers.

**Before setting `next_steps` or `status` on a project doc that has other active threads:** read the existing section, merge your items into it, and emit the merged body. Sub-headings (`### Buildout`, `### Documents to sign`) keep threads separate inside one section and make the merge obvious next time.

**The helper now warns.** Since 2026-08-30 a `next_steps` replace that drops existing lines prints them to stderr under its own banner. Set `next_steps_replace_ok: true` to silence it when the discard is deliberate. `status` is deliberately not guarded, since replacing a current-state line is what that field is for.

---

## Common Mistakes — Read Before Using This Skill

1. **`obsidian update` does not exist.** There is no update command. To overwrite an existing file, use the **Write tool** targeting the full filesystem path (e.g. `~/Documents/<VAULT_NAME>/Context/current-focus.md`). Using `obsidian update` will fail silently or error out.
2. **New file vs. overwrite.** Use `obsidian create` only for files that do not exist yet. For files that already exist, use the Write tool. See the "File Write Decision Tree" section in SKILL.md.
3. **Vault path resolution.** The `obsidian` CLI commands use the vault *name* (e.g. `vault="Claude Code Obsidian"`). The Write tool needs the full *filesystem path*. These are different. See "Vault Location" in SKILL.md.
4. **Write tool requires an ABSOLUTE filesystem path — `~` is not expanded.** This bites every Claude Code session that writes to vault files because the rest of the skill (and the obsidian CLI) tolerate `~/Documents/...`. The Write tool does not — it tries to write to a literal `~/Documents/...` directory and fails with the generic "Error writing file" message. Always pass the resolved absolute path: `/Users/<username>/Documents/<VAULT_NAME>/<rest>`. On Mo's machine: `/Users/mohannadarbaji/Documents/Claude Code Obsidian/<rest>`.
5. **Write tool requires you to Read the file first.** Harness safeguard. If you call Write on a file you haven't Read in the current session, you get `File has not been read yet. Read it first before writing to it.` Fix: do a 5-line `Read` first, then Write. Counts even for files Claude itself just created via `obsidian create` earlier in the session.
6. **Never skip the session-end approval step.** Writing project docs with wrong categories (ChalkTalk vs Personal) is a high-consequence error. Always present the summary and wait for user confirmation before writing anything.
7. **Wrong `obsidian` binary on PATH (npm `obsidian-cli@0.5.1` shadowing the native one).** Symptom: `obsidian create ...` errors with `An API key must be provided via -apikey or an environment variable called OBSIDIAN_API_KEY!`. Cause: the npm package `obsidian-cli` is the **Obsidianqa.com testing CLI** — a completely different tool that happens to install a binary named `obsidian` at `/opt/homebrew/bin/obsidian`. The right tool is the native vault CLI at `/usr/local/bin/obsidian` (a symlink to `/Applications/Obsidian.app/Contents/MacOS/obsidian-cli`) which talks to the running Obsidian app via `~/.obsidian-cli.sock`. Fix: `npm uninstall -g obsidian-cli`. Verify with `which obsidian` (should be `/usr/local/bin/obsidian`) and `obsidian vaults` (should list the user's vault names, not error about an API key). Resolved 2026-04-30 mo session.
8. **The skill can load from a STALE plugin cache while a current one exists — verify the loaded `references/` before following the ritual.** Symptom: you follow the session-end ritual and it is missing rules you know were added. Cause: Claude Code resolves the plugin to one cache dir for the session (`~/.claude/plugins/cache/marbaji-claude/marbaji-claude/<sha>/`), and if the plugin version did not bump it can keep an older dir even though a newer one is present alongside it. Observed 2026-07-31: the loaded `references/session-end.md` was **35,750 chars against the marketplace clone's 38,074** — 2,324 chars behind, missing the "resolve New-person mentions yourself, never ask the user whether a People note exists" rule and the "every extraction bucket carries a count with 0s shown" formatting contract. Both would have produced a visibly wrong session-end. Fix: before following any multi-step ritual from this skill, diff the loaded reference against the clone and prefer the clone if they differ:
   ```bash
   C=$(ls -dt ~/.claude/plugins/cache/marbaji-claude/marbaji-claude/*/ | head -1)
   M=~/.claude/plugins/marketplaces/marbaji-claude
   diff -q "$C/skills/obsidian-memory/references/session-end.md" \
           "$M/skills/obsidian-memory/references/session-end.md" || echo "CACHE STALE — read from $M"
   ```
   The same applies to `helpers/session_end.py`: the stale cache lacked `--print-schema` / `--example` entirely, so a ritual run from it would fall back to reading the 43 KB prose schema.
9. **`mcp__qmd__get` takes `file`, not `path`.** The sibling retrieval tools and the rest of this skill talk in terms of vault *paths*, so `path=` is the natural guess and it fails Pydantic validation with `Invalid arguments for tool get: expected string, received undefined` on `file`. Correct form: `mcp__qmd__get(file="obsidian-memory/personal/projects/<slug>/overview.md")`. Note also that qmd's returned paths are lowercased relative to the collection, so a result path is not always the on-disk path — resolve the real directory name with `ls` before passing it to Edit or Write (e.g. qmd reports `personal/projects/inbloom-early-learning/` where disk has `Personal/Projects/InBloom Early Learning/`). Observed 2026-08-18.
10. **Direct filesystem access to the vault can hit macOS `EPERM` mid-session — even after working earlier in the same session.** Symptom: Bash `cat`/`ls` and the Read/Write tools all return `operation not permitted` on vault paths under `~/Documents/`, while the same paths read fine minutes before (TCC/sandbox behavior is non-deterministic per process; a helper run in a Python subprocess may still succeed while the shell is blocked). Fix: fall back to the native `obsidian` CLI (`obsidian vault="<name>" read|create|append path="..."`), which talks to the running Obsidian app over its socket and bypasses the filesystem permission entirely. Retry direct access later — the block can clear within the same session. Observed 2026-07-29 (chalktalk lesson-plan-maker session: CR-learnings ledger append EPERM'd via shell + Write, succeeded via `obsidian append`; taxonomy-ledger edits worked directly ten minutes later).
