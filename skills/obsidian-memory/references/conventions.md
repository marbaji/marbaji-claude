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
cat ~/.claude/obsidian-vault-name  # Check configured vault name
```

To reconfigure vault:
```bash
rm ~/.claude/obsidian-vault-name
# Then invoke the skill again — setup flow will run
```

For deeper failure modes (wrong `obsidian` binary on PATH, Write tool path expansion, etc.), see `references/gotchas.md`.

## Integration with Other Skills

- **TodoWrite**: Track multi-step tasks, then summarize in session log
- **inventory-checker**: Document setup changes in Technical/Setup/
