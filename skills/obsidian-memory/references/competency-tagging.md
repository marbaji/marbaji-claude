# Competency Evidence Tagging

**When to use**: When a session demonstrates a team member performing in a way that maps to one of their role's competencies (e.g., a PR review showed strong attention to detail; a debugging call showed clear collaboration; an incident response showed bias to action).

## What to do

1. Identify (a) the person, (b) the competency note that matches their demonstrated behavior, (c) the value (if any) the behavior aligns with.
2. In the relevant section of the session log (typically `## Learnings` or `## Key Decisions`), insert a wikilink to the competency note: `Demonstrated [[<YourOrg>/Competencies/<role-folder>/<Competency>|<Competency>]] (<First Name>) when <one-line context>.`
3. If the behavior strongly aligns with a value, also link the relevant section of `[[<YourOrg>/Values]]`.

This is **lightweight tagging in prose**, not a separate file. The competency note's `## Evidence` section auto-aggregates these mentions via Obsidian's backlinks panel — no manual edits to the competency note are needed.

## When NOT to tag

- Routine task completion (shipping a small bug fix is not "demonstrating attention to detail")
- Behavior already captured by a Decision or 1:1 note that already links the competency
- Cross-team / non-employee references (don't tag external collaborators against your company's competencies)

The `employee-review` skill walks these backlinks to score reviews. Quality > quantity — fabricated or inflated tags weaken the signal.
