# Gotchas

Failure points accumulated from real runs of the `obsidian-memory` skill. Add an entry every time the skill hits a surprising failure — wrong CLI subcommand, vault path confusion, missing approval step, etc.

---

## Common Mistakes — Read Before Using This Skill

1. **`obsidian update` does not exist.** There is no update command. To overwrite an existing file, use the **Write tool** targeting the full filesystem path (e.g. `~/Documents/<VAULT_NAME>/Context/current-focus.md`). Using `obsidian update` will fail silently or error out.
2. **New file vs. overwrite.** Use `obsidian create` only for files that do not exist yet. For files that already exist, use the Write tool. See the "File Write Decision Tree" section in SKILL.md.
3. **Vault path resolution.** The `obsidian` CLI commands use the vault *name* (e.g. `vault="Claude Code Obsidian"`). The Write tool needs the full *filesystem path* (e.g. `~/Documents/Claude Code Obsidian/Context/current-focus.md`). These are different. See "Vault Location" in SKILL.md.
4. **Never skip the session-end approval step.** Writing project docs with wrong categories (ChalkTalk vs Personal) is a high-consequence error. Always present the summary and wait for user confirmation before writing anything.
