# File Operations

Before writing to any file, follow this decision tree.

| Scenario | Tool to Use | Example |
|---|---|---|
| **New file** (does not exist yet) | `obsidian create` | `obsidian create path="Work/Chalktalk/Projects/new-project.md" content="..." vault="<VAULT_NAME>"` |
| **Overwrite existing file** | **Write tool** (resolved absolute path; Read first) | Write tool targeting `/Users/<username>/Documents/<VAULT_NAME>/Context/current-focus.md` (NOT `~/Documents/...` — see SKILL.md "Vault Location" for why) |
| **Append to existing file** | `obsidian append` | `obsidian append file="Technical/Learnings/lessons-learned" content="..." vault="<VAULT_NAME>"` |
| **Update frontmatter property** | `obsidian property:set` | `obsidian property:set file="..." property="status" value="complete" vault="<VAULT_NAME>"` |

> **WARNING:** `obsidian update` does not exist. Never use it. If you need to change an existing file's content, read it first, then use the Write tool to overwrite it at the full filesystem path.

## File Modification Notes

- `obsidian update` does not exist. To overwrite files, use the Write tool on the full vault path
- `obsidian append` works for adding to the end of a file
- `obsidian create` works for new files
- `obsidian property:set` works for updating frontmatter properties
