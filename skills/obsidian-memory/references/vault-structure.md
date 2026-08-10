# Vault Structure

```
Context/
  about-me.md              — Who the user is (work, personal, background)
  current-focus.md         — Active/ongoing/complete projects with wikilinks
  preferences.md           — Working style preferences
  work-context.md          — Domain knowledge
  Project Backlog.md       — Manually maintained by user. Read-only for Claude.

Work/Chalktalk/Projects/
  project-name.md          — One file per ChalkTalk work project

# Org-and-perf folders below. Replace `<YourOrg>` with your company's
# folder name in your own vault adoption (e.g. Work/Acme/People/). The skill
# does not hardcode any specific org name; adopt the pattern that fits your
# vault. See references/adopting-this-skill.md for the full adoption guide.

<YourOrg>/People/          — One note per team member; backlinks aggregate 1:1s + competency evidence
  <first-last>.md          — See references/people-template.md for schema
  _index.md                — Folder index

<YourOrg>/Departments/     — Top-level org units with head + sub-teams + member roster
  <Department Name>.md     — One per top-level dept
  _index.md

<YourOrg>/Competencies/    — Competency notes mirrored from your company's role scorecards
  <Role Folder>/<Competency>.md  — See references/competency-template.md for schema
  _index.md (top-level + per-role)

<YourOrg>/1-on-1s/         — Dated 1:1 meeting notes; folder scaffolded; capture flow is future work
  <First Name> YYYY-MM-DD.md  — See references/one-on-one-template.md
  _index.md

<YourOrg>/Decisions/       — Decisions of lasting consequence; auto-extracted by session-end ritual
  YYYY-MM-DD-<slug>.md     — See references/decision-template.md
  _index.md

<YourOrg>/Reviews/         — Employee review drafts produced by the employee-review skill
  <period>/<First Last>.md
  _index.md

<YourOrg>/Values.md        — Your company's values; link target for value-aligned work
<YourOrg>/Shipping Log.md  — Date-ordered log of what your company shipped; feeds board/investor updates

Personal/Projects/
  ProjectName/             — Subfolder per personal project (e.g. InBloom Early Learning/)
    overview.md            — Main project doc
    (other docs as needed)

Personal/Brag Doc.md       — User's running log of personal wins; separate from the company Shipping Log
Personal/Brag Archive.md   — Culled brag candidates, archived monthly by the promotion pass; created on first cull
Personal/Quarterly Reviews/  — Cross-quarter syntheses produced by the quarterly-review skill
  YYYY-Q[1-4].md

Sources/
  YYYY-MM-DD-description.md  — URL source files with summary + takeaways

Sessions/YYYY-MM/
  YYYY-MM-DD-topic.md      — Session logs with wikilinks to projects

Technical/
  Learnings/               — Technical notes and lessons
  Setup/                   — Tool/environment documentation

Templates/
  project.md, session-log.md, etc.
```

---

## Project Backlog

The file `Context/Project Backlog.md` is **manually maintained by the user**. It contains:
- Prioritized list of projects the user wants to work on
- Tool references and tips
- Backlog of content/tooling projects to pull from

**Rules**:
- **Read** it at session start for awareness of priorities
- **Never modify** it — the user updates this themselves
- **Reference** it when suggesting what to work on next
- If a backlog item gets started, create a proper project doc in `Work/Chalktalk/Projects/` — don't modify the backlog
- **Cross-reference** when creating new project docs: check if the project maps to a backlog item. If it does, note the backlog reference in the project doc's Overview section (e.g., "This project addresses backlog item #1: '...'"). This links project docs back to the user's original priorities.
