# Conventions, Troubleshooting, Integration

## File Naming Conventions

- Sessions: `YYYY-MM-DD-description.md`
- Work projects: `project-name.md` (in `Work/Chalktalk/Projects/`)
- Personal projects: `overview.md` (in `Personal/Projects/<ProjectName>/`)
- Ideas: `idea-name.md`

## Tags to Use

- `#work/chalktalk` — ChalkTalk work
- `#personal` — Personal projects
- `#technical` — Technical notes
- `#decision` — Important decision made
- `#lesson-learned` — Key learning or insight
- `#blocker` — Something blocking progress
- `#idea` — Ideas and brainstorms

## Troubleshooting

If obsidian command not found:
```bash
source ~/.zshrc
```

If vault not found:
```bash
obsidian vaults  # List all vaults
cat ~/.claude/obsidian-vault-path 2>/dev/null  # Check configured vault path (canonical, post-2026-05)
cat ~/.claude/obsidian-vault-name 2>/dev/null  # Legacy fallback (pre-2026-05 setups)
```

To reconfigure vault — remove BOTH config files so the setup wizard runs cleanly:
```bash
rm -f ~/.claude/obsidian-vault-path ~/.claude/obsidian-vault-name
# Optionally also reset the org name:
# rm -f ~/.claude/obsidian-org-name
# Then invoke the skill again — setup flow will run
```

For deeper failure modes (wrong `obsidian` binary on PATH, Write tool path expansion, etc.), see `references/gotchas.md`.

## Integration with Other Skills

- **TodoWrite**: Track multi-step tasks, then summarize in session log
- **inventory-checker**: Document setup changes in Technical/Setup/
