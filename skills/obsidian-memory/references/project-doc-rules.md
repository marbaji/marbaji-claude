# Project Doc Update Rules

These rules keep project docs useful without them becoming stale or bloated.

## Status Values

Use in frontmatter `status` field:
- `active` — Currently being worked on
- `ongoing` — Maintenance/recurring work, no end date
- `complete` — Done, no remaining work
- `blocked` — Waiting on something external

## Sections That Get Replaced (not appended)

- **Next Steps** — Always reflects the latest state. Old next steps are gone.
- **Status** — Reflects current reality.

## Sections That Get Prepended (most recent first)

- **Recent Work** — Add today's entry at the top. Keep last 3 entries. Trim older ones to keep the doc from growing forever.

## Sections That Get Appended

- **Related Sessions** — Add wikilink to today's session at the bottom.

## Sections That Only Change When Materially Different

- **Overview**, **Key Findings**, **Technical Details**, **Project Directory** — Only update if something actually changed (e.g., new key finding, moved directory).

## When to Mark Complete

- User explicitly says "this is done" or "project complete"
- All next steps are resolved with no new ones emerging
- When in doubt, leave as active and ask
