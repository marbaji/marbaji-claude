# session_end.py — reference

`session_end.py` is the Obsidian-vault write engine for the obsidian-memory skill's session-end phase. It accepts a YAML manifest that the agent emits at the end of every session, validates the manifest against a Pydantic v2 schema, runs a preflight check against the live vault to surface any collision or missing-file problems before touching anything, and then atomically writes between 1 and 12 markdown artifacts: a session log, decision files, shipping-log bullets, brag-doc bullets, project-doc appends, new project docs, and focus-file edits. It is designed to be all-or-nothing in the common failure case — if preflight finds any problem, no writes happen, making retries safe.

---

## CLI

```
python3 session_end.py --manifest <path> [--dry-run] [--vault-path <path>] [--only <sections>]
```

| Flag | Type | Required | Description |
|---|---|---|---|
| `--manifest` | `Path` | Yes | Path to the YAML manifest file. Typically `/tmp/session-end-<ts>.yaml`. |
| `--dry-run` | flag | No | Print what would be written without touching any file. Preflight still runs. |
| `--vault-path` | `Path` | No | Override the vault path. When omitted, resolved from `~/.claude/obsidian-vault-path` (or legacy `~/.claude/obsidian-vault-name`). |
| `--only` | `str` (comma-separated) | No | Run only the named sections. Valid values: `session_log`, `extractions`, `project_doc_updates`, `new_project_docs`, `focus_updates`. Omit to run all five. |

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All writes succeeded (or dry-run completed with no problems found). |
| `1` | Manifest could not be read (file missing, YAML parse error) or failed Pydantic validation. No writes attempted. |
| `2` | Preflight failure (missing target file, collision for new project doc) or a file-write error encountered mid-run. |
| `3` | Vault not found — `--vault-path` was not given, `~/.claude/obsidian-vault-path` is absent or empty, and the legacy `~/.claude/obsidian-vault-name` fallback also failed. |

---

## Manifest schema

### Top-level fields

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `date` | `date` (ISO 8601) | Required | Must be a valid date string parseable by Pydantic's `date` type. | `2026-05-09` |
| `topic` | `str` | Required | Pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$` (kebab-case, lowercase). | `session-end-helper-docs` |
| `tags` | `list[str]` | Required | Non-empty list; no pattern constraint on individual tags. | `[obsidian-memory, docs]` |
| `last_updated_slug` | `str` | Required | No pattern constraint; written verbatim into `last-updated:` frontmatter of `current-focus.md`. | `2026-05-09-session-end-helper` |
| `summary` | `str` | Required | Any markdown. Rendered under `## Summary` in the session log. | `"Wrote the session_end.py reference doc."` |
| `projects_touched` | `list[ProjectTouched]` | Required | At least one entry expected; each entry has `slug` + `note`. | See `ProjectTouched` below. |
| `streams` | `list[Stream]` | Required | At least one entry expected; each entry has `title` + `body`. | See `Stream` below. |
| `key_decisions` | `str` | Required | Any markdown. Rendered under `## Key Decisions` in the session log. | `"No blocking decisions."` |
| `learnings` | `str` | Required | Any markdown. Rendered under `## Learnings` in the session log. | `"Pydantic alias fields require model_config populate_by_name."` |
| `files_modified` | `FilesModified` | Required | Nested object; see `FilesModified` below. | See below. |
| `next_steps` | `str` | Required | Any markdown. Rendered under `## Next Steps` in the session log. | `"Commit and open PR."` |
| `sources_captured` | `list[Source]` | Optional (default `[]`) | Each entry has `url`, `title`, `why`. | See `Source` below. |
| `extractions` | `Extractions` | Optional (default empty) | Nested object; see `Extractions` below. | See below. |
| `project_doc_updates` | `list[ProjectDocUpdate]` | Optional (default `[]`) | Each entry updates an existing project doc. | See `ProjectDocUpdate` below. |
| `new_project_docs` | `list[NewProjectDoc]` | Optional (default `[]`) | Each entry creates a new project doc. | See `NewProjectDoc` below. |
| `focus_updates` | `FocusUpdates` | Optional (default all-empty) | Controls edits to `current-focus.md`. | See `FocusUpdates` below. |

---

### ProjectTouched

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `slug` | `str` | Required | Pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$` | `obsidian-memory` |
| `note` | `str` | Required | Free text. | `"Wrote session-end-helper.md reference doc."` |

---

### Stream

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `title` | `str` | Required | Free text; emitted as `### <title>` under `## What We Did`. | `"Reference doc authoring"` |
| `body` | `str` | Required | Any markdown, including `### / ####` sub-headings. Preserved verbatim. | `"Read session_end.py, then wrote the full schema reference."` |

---

### FilesModified

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `chalktalk` | `list[FilesModifiedRepo]` | Optional (default `[]`) | Commits in the `chalktalk` repo. | See `FilesModifiedRepo` below. |
| `marbaji-claude` | `list[FilesModifiedRepo]` | Optional (default `[]`) | Commits in the `marbaji-claude` repo. **Note:** YAML key is `marbaji-claude` (with a hyphen); the Pydantic alias is `marbaji_claude` internally. Either form is accepted in YAML due to `populate_by_name: True`. | See `FilesModifiedRepo` below. |
| `other` | `dict[str, list[FilesModifiedRepo]]` | Optional (default `{}`) | Key is any repo name; value is a list of commits. | `{some-other-repo: [{message: "fix typo"}]}` |
| `local` | `str` or `null` | Optional (default `null`) | Free-text description of local-only file changes. | `"Updated ~/notes/scratch.md"` |

---

### FilesModifiedRepo

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `sha` | `str` or `null` | Optional | Short or full commit SHA. | `7b6de41` |
| `pr` | `int` or `null` | Optional | PR number. | `50` |
| `message` | `str` | Required | Commit message or change description. | `"docs(obsidian-memory): add session-end-helper reference"` |

---

### Source

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `url` | `str` | Required | Full URL. | `https://docs.pydantic.dev/latest/` |
| `title` | `str` | Required | Display title. | `"Pydantic v2 docs"` |
| `why` | `str` | Required | Reason this source is relevant. | `"Verified alias field behavior"` |

---

### Extractions

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `decisions` | `list[Decision]` | Optional (default `[]`) | Each entry produces one `Decisions/<slug>.md` file. | See `Decision` below. |
| `shipping_log` | `list[ShippingEntry]` | Optional (default `[]`) | Each entry appends one bullet to `Shipping Log.md`. | See `ShippingEntry` below. |
| `brag` | `list[BragEntry]` | Optional (default `[]`) | Each entry appends one bullet to `Brag Doc.md`. | See `BragEntry` below. |
| `new_people` | `list[NewPersonFlag]` | Optional (default `[]`) | Each entry is printed to stdout as a flag; no file is written. | See `NewPersonFlag` below. |

---

### Decision

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `slug` | `str` | Required | Matches `^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$` (dated) OR `^[a-z0-9]+(?:-[a-z0-9]+)*$` (undated). Undated slugs inherit the session date as filename prefix. | `use-pydantic-for-schema-validation` |
| `title` | `str` | Required | Full decision title. Rendered as `# <title>`. | `"Use Pydantic v2 for manifest validation"` |
| `status` | `str` | Optional (default `accepted`) | Pattern `^(proposed\|accepted\|superseded\|deprecated)$` | `accepted` |
| `owner` | `str` | Required | Wikilink or plain name. | `[[Mohannad Arbaji]]` |
| `stakeholders` | `list[str]` | Optional (default `[]`) | List of wikilinks or plain names. | `[[[Ciaran OBrien]]]` |
| `supersedes` | `str` or `null` | Optional (default `null`) | Wikilink to the decision this replaces. | `[[2025-11-01-use-json-schema]]` |
| `tags` | `list[str]` | Optional (default `["decision"]`) | Tag list for frontmatter. | `[decision, architecture]` |
| `context` | `str` | Required | Background and problem statement. | `"Manual YAML parsing was fragile..."` |
| `options_considered` | `str` | Required | Alternatives explored. | `"1. dataclasses, 2. Pydantic, 3. marshmallow"` |
| `chosen` | `str` | Required | Which option was chosen. | `"Pydantic v2"` |
| `reasoning` | `str` | Required | Why this option was chosen. | `"Best validation ergonomics and alias support."` |
| `consequences` | `str` | Required | Trade-offs and follow-on effects. | `"Requires pydantic>=2 in environment."` |

**Frontmatter `date:` rule:** Always emitted. For dated slugs, the date is extracted from the slug prefix (e.g. `2026-05-09-foo` → `date: 2026-05-09`). For undated slugs, the session's `date` field is used. This keeps the filename and frontmatter consistent (Codex adversarial-review finding #2).

**Collision behavior:** If the resolved output path already exists, the write is skipped with a stderr warning — no overwrite. If two slugs in the same run resolve to the same output path, the later entry wins (stderr warning emitted).

---

### ShippingEntry

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `date` | `date` | Required | ISO 8601 date. | `2026-05-09` |
| `label` | `str` | Required | Short description of the shipped item. | `"session-end-helper reference doc"` |
| `project_slug` | `str` or `null` | Optional (default `null`) | Not used in the rendered bullet currently; reserved for future filtering. | `obsidian-memory` |
| `context` | `str` or `null` | Optional (default `null`) | Extra context appended to the bullet before the session wikilink. | `"Task 15 of 15 in the session-end CLI plan"` |

---

### BragEntry

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `quarter` | `str` | Required | Pattern `^\d{4} Q[1-4]$` (e.g. `2026 Q2`). | `2026 Q2` |
| `date` | `date` | Required | ISO 8601 date of the achievement. | `2026-05-09` |
| `body` | `str` | Required | One-line or short description of the achievement. Trailing period is stripped before appending the session wikilink. | `"Shipped session_end.py with 47 passing tests"` |

---

### NewPersonFlag

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `name` | `str` | Required | Person's name. | `"Alex Kim"` |
| `why_flagged` | `str` | Required | Reason to create a People note. | `"New stakeholder introduced during session"` |

No file is written for `new_people` entries — the helper prints a stdout flag and expects the operator to create the note manually.

---

### ProjectDocUpdate

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `slug` | `str` | Required | Pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$`. Must match an existing `Work/<Org>/Projects/<slug>.md` or preflight fails with exit 2. | `obsidian-memory` |
| `section_title` | `str` | Required | Heading text; rendered as `## YYYY-MM-DD — <section_title>`. | `"session-end-helper shipped"` |
| `section_date` | `date` | Required | ISO 8601 date for the section heading. | `2026-05-09` |
| `body` | `str` | Required | Section body. Appended verbatim after the heading. | `"All 15 tasks complete. PR opened."` |

---

### NewProjectDoc

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `slug` | `str` | Required | Pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$`. Must NOT exist in the vault or preflight fails with exit 2. | `new-initiative` |
| `frontmatter` | `dict` | Required | Arbitrary key-value pairs serialized to YAML frontmatter. | `{status: active, owner: "[[Mohannad Arbaji]]"}` |
| `body` | `str` | Required | Document body below the frontmatter. | `"# New Initiative\n\nKickoff notes."` |

---

### FocusUpdates

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `remove` | `list[str]` | Optional (default `[]`) | Project slugs whose entry blocks are deleted from `current-focus.md`. | `[old-project]` |
| `upsert` | `list[FocusUpsert]` | Optional (default `[]`) | Entries to insert or replace at the top of `## Active Projects`. | See `FocusUpsert` below. |
| `move_to_complete` | `list[str]` | Optional (default `[]`) | Project slugs whose blocks are moved to `## Complete` with a `✅` suffix appended to the heading line. | `[finished-project]` |

Operations are applied in order: removes first, then move-to-complete, then upserts.

---

### FocusUpsert

| Field | Type | Req/Opt | Validation | Example |
|---|---|---|---|---|
| `slug` | `str` | Required | Pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$`. | `obsidian-memory` |
| `status_line` | `str` | Required | Single-line status written directly below the `### [[...]]` heading. | `"Writing session-end reference docs — Task 15/15 in progress."` |

---

## Section-by-section behavior

| Manifest field(s) | Section name | What gets written / where |
|---|---|---|
| `summary`, `projects_touched`, `streams`, `key_decisions`, `learnings`, `files_modified`, `sources_captured`, `next_steps` | `session_log` | `Sessions/YYYY-MM/YYYY-MM-DD-<topic>.md` — new file; parent directory created if absent. |
| `extractions.decisions[]` | `extractions` | `Work/<Org>/Decisions/<slug>.md` — one file per entry (dated slug used verbatim; undated slug prefixed with session date). Skip-with-warning on collision; no overwrite. |
| `extractions.shipping_log[]` | `extractions` | `Work/<Org>/Shipping Log.md` — one bullet inserted immediately after the `## YYYY-MM` heading. Heading is created at top of first `## ` block if absent. File must exist or preflight fails. |
| `extractions.brag[]` | `extractions` | `Personal/Brag Doc.md` — one bullet inserted immediately after the `## YYYY Q<N>` heading. Heading created if absent. File must exist or preflight fails. |
| `extractions.new_people[]` | `extractions` | Stdout only — flag printed, no file written. Operator creates People notes manually. |
| `project_doc_updates[]` | `project_doc_updates` | Append `## YYYY-MM-DD — <section_title>` section to `Work/<Org>/Projects/<slug>.md`. Preflight fails with exit 2 if file does not exist. |
| `new_project_docs[]` | `new_project_docs` | Write new `Work/<Org>/Projects/<slug>.md` with YAML frontmatter + body. Preflight fails with exit 2 if file already exists. |
| `focus_updates.*` | `focus_updates` | Edit `Context/current-focus.md`: remove blocks, move blocks to `## Complete` (with `✅`), upsert at top of `## Active Projects`. Always bumps `last-updated:` frontmatter field from `last_updated_slug`. File must exist or preflight fails. |

---

## Worked examples

### Example 1: Minimum viable (single-stream session, no extractions)

No extractions, no project-doc changes, no focus edits. Only a session log is written.

```yaml
date: 2026-05-09
topic: quick-bug-fix
tags: [bug-fix, chalktalk]
last_updated_slug: 2026-05-09-quick-bug-fix
summary: Fixed a null-pointer in the renewal storytelling skill's PDF renderer.
projects_touched:
  - slug: renewal-storytelling
    note: "Patched PDF renderer null-pointer on missing district data."
streams:
  - title: Bug fix
    body: |
      Traced the failure to `render_pdf.py` line 42 — missing guard on
      `district.name`. Added a fallback to `"Unknown District"`.
key_decisions: No architectural decisions — single-line guard added.
learnings: Always guard optional fields before string interpolation in Jinja templates.
files_modified:
  chalktalk:
    - sha: abc1234
      pr: 101
      message: "fix(renewal): guard district.name in PDF renderer"
  marbaji-claude: []
next_steps: Monitor next renewal run to confirm no recurrence.
```

Invocation:

```bash
python3 ~/.claude/plugins/marketplaces/marbaji-claude/skills/obsidian-memory/helpers/session_end.py \
  --manifest /tmp/session-end-20260509.yaml
```

Artifacts written:
- `Sessions/2026-05/2026-05-09-quick-bug-fix.md`

---

### Example 2: Full coverage (multi-stream, all extractions, project changes, focus update)

```yaml
date: 2026-05-09
topic: session-end-helper-full
tags: [obsidian-memory, architecture, shipping]
last_updated_slug: 2026-05-09-session-end-helper-full
summary: |
  Completed the session-end CLI helper (Tasks 1-15): Pydantic schema, vault write
  engine, preflight validation, 47 tests, and this reference doc.
projects_touched:
  - slug: obsidian-memory
    note: "All 15 tasks complete; PR #50 open."
  - slug: renewal-storytelling
    note: "No changes this session; monitored only."
streams:
  - title: Schema design and Pydantic models
    body: |
      Designed 14 Pydantic models covering every manifest field.
      Key challenge: `marbaji-claude` YAML key mapped via alias field.

      ### Alias field resolution
      Used `model_config = {"populate_by_name": True}` so both
      `marbaji-claude` (YAML) and `marbaji_claude` (Python) are accepted.
  - title: Vault write engine
    body: |
      Implemented 8 write functions: `render_session_log`, `write_decision_files`,
      `append_to_shipping_log`, `append_to_brag_doc`, `append_to_project_doc`,
      `write_new_project_doc`, `process_focus_updates`, and the preflight gate.
  - title: Test suite
    body: |
      47 tests across 6 files. All passing on Python 3.11 and 3.12.
key_decisions: |
  - Preflight runs before any write, making the helper all-or-nothing on common failures.
  - Decision-file collisions are warned (not blocked) at write time; same-run
    path collisions are surfaced in preflight.
  - Undated decision slugs inherit the session date for both filename and frontmatter.
learnings: |
  - Pydantic v2 alias fields require `model_config = {"populate_by_name": True}` to
    accept both the alias and the Python attribute name.
  - `sys.executable` must be used in subprocess helpers to avoid hardcoded Python paths
    in CI (PR #50 fix `7b6de41`).
files_modified:
  chalktalk: []
  marbaji-claude:
    - sha: 7b6de41
      pr: 50
      message: "feat(obsidian-memory): add session_end.py helper with full test suite"
    - sha: a1b2c3d
      pr: 50
      message: "docs(obsidian-memory): add session-end-helper reference"
  other: {}
  local: "Tested against ~/Documents/Claude Code Obsidian vault."
sources_captured:
  - url: https://docs.pydantic.dev/latest/concepts/fields/#field-aliases
    title: "Pydantic v2 — Field aliases"
    why: "Verified alias + populate_by_name behavior for marbaji-claude field."
  - url: https://docs.python.org/3/library/argparse.html
    title: "Python argparse docs"
    why: "Confirmed argparse.ArgumentTypeError usage for --only validation."
next_steps: |
  - Wait for CodeRabbit review on PR #50.
  - Address any review comments and re-request review.
  - Merge once re-review is clean.
extractions:
  decisions:
    - slug: preflight-before-writes
      title: "Run preflight validation before any vault write"
      status: accepted
      owner: "[[Mohannad Arbaji]]"
      stakeholders: []
      tags: [decision, architecture, obsidian-memory]
      context: |
        Without preflight, a failure mid-run (e.g. missing project doc) leaves the
        vault partially modified, making retries unsafe (duplicate appends).
      options_considered: |
        1. Write and roll back on failure (complex).
        2. Preflight everything first, then write atomically (simple, safe).
      chosen: "Preflight-first approach."
      reasoning: |
        Preflight is stateless and fast; it surfaces ALL problems before any write,
        so operators fix the manifest once and retry cleanly.
      consequences: |
        Partial runs are not possible on ordinary failures. The --only flag
        limits preflight scope to active sections only.
    - slug: 2026-05-09-skip-collision-with-warning
      title: "Skip decision-file collisions with stderr warning, no overwrite"
      status: accepted
      owner: "[[Mohannad Arbaji]]"
      stakeholders: []
      tags: [decision, obsidian-memory]
      context: "Decision files are immutable once written; overwriting could lose history."
      options_considered: |
        1. Hard error on collision (safe but blocking).
        2. Skip with warning (safe, non-blocking, preserves existing file).
      chosen: "Skip with warning."
      reasoning: "Existing decision files represent recorded history and must not be overwritten."
      consequences: "Operator must rename the slug if the collision was unintentional."
  shipping_log:
    - date: 2026-05-09
      label: "session_end.py helper — 47 tests, full vault write engine"
      project_slug: obsidian-memory
      context: "Tasks 1-15 of the session-end CLI plan"
  brag:
    - quarter: 2026 Q2
      date: 2026-05-09
      body: "Shipped session_end.py (15 tasks, 47 tests) — obsidian-memory vault write engine"
  new_people: []
project_doc_updates:
  - slug: obsidian-memory
    section_title: "session-end CLI helper shipped"
    section_date: 2026-05-09
    body: |
      All 15 tasks complete. session_end.py is fully functional with 47 passing tests.
      PR #50 open for review. Reference doc at references/session-end-helper.md.
new_project_docs: []
focus_updates:
  remove: []
  upsert:
    - slug: obsidian-memory
      status_line: "session_end.py PR #50 open — awaiting CodeRabbit review."
  move_to_complete: []
```

Invocation (all sections, normal run):

```bash
python3 ~/.claude/plugins/marketplaces/marbaji-claude/skills/obsidian-memory/helpers/session_end.py \
  --manifest /tmp/session-end-20260509-full.yaml
```

Artifacts written:
- `Sessions/2026-05/2026-05-09-session-end-helper-full.md`
- `Work/Chalktalk/Decisions/2026-05-09-preflight-before-writes.md`
- `Work/Chalktalk/Decisions/2026-05-09-skip-collision-with-warning.md`
- `Work/Chalktalk/Shipping Log.md` — one bullet appended under `## 2026-05`
- `Personal/Brag Doc.md` — one bullet appended under `## 2026 Q2`
- `Work/Chalktalk/Projects/obsidian-memory.md` — one section appended
- `Context/current-focus.md` — `obsidian-memory` block upserted, `last-updated:` bumped

---

### Example 3: Project-doc-only partial run

Use `--only project_doc_updates` to append a section to an existing project doc without touching the session log, extractions, or focus file. Useful when a post-session update arrives after the main session-end run has already completed.

```yaml
date: 2026-05-09
topic: obsidian-memory-followup
tags: [obsidian-memory]
last_updated_slug: 2026-05-09-obsidian-memory-followup
summary: Post-session follow-up note only.
projects_touched:
  - slug: obsidian-memory
    note: "Post-session addendum after CodeRabbit review."
streams:
  - title: Follow-up
    body: CodeRabbit flagged one issue with sys.executable — fixed and pushed.
key_decisions: No new decisions.
learnings: CodeRabbit catches hardcoded interpreter paths in subprocess helpers.
files_modified:
  chalktalk: []
  marbaji-claude:
    - sha: 7b6de41
      message: "fix: use sys.executable in test subprocess helper"
next_steps: Wait for re-review, then merge.
project_doc_updates:
  - slug: obsidian-memory
    section_title: "CodeRabbit fix — sys.executable"
    section_date: 2026-05-09
    body: |
      Fixed hardcoded `/opt/homebrew/bin/python3` in test helper after CR review.
      Commit `7b6de41` on PR #50.
```

Invocation:

```bash
python3 ~/.claude/plugins/marketplaces/marbaji-claude/skills/obsidian-memory/helpers/session_end.py \
  --manifest /tmp/session-end-followup.yaml \
  --only project_doc_updates
```

Artifacts written:
- `Work/Chalktalk/Projects/obsidian-memory.md` — one section appended

Nothing else is touched. If `obsidian-memory.md` does not exist, preflight exits with code 2 before any write.

---

## Conventions

- **Manifest path:** Use `/tmp/session-end-<timestamp>.yaml` (e.g. `/tmp/session-end-20260509T143000.yaml`). The file is ephemeral — the helper reads it once and exits; the agent may delete it after a successful run.
- **Vault path:** Resolved in priority order: (1) `--vault-path` CLI flag, (2) contents of `~/.claude/obsidian-vault-path` (canonical, post-2026-05), (3) `~/Documents/<name>` where `<name>` comes from `~/.claude/obsidian-vault-name` (legacy fallback).
- **Org name:** Read from `~/.claude/obsidian-org-name`. Defaults to `Chalktalk` if the file is absent. Used in all `Work/<Org>/...` paths.
- **`current-focus.md` upsert insertion point:** New upsert blocks are inserted immediately after the `## Active Projects` heading line (at index `active_idx + 1`), pushing any existing content down. If the heading does not exist, it is appended at end of file.
- **Decision-file collision:** An existing file at the resolved path is skipped with a stderr warning. The helper never overwrites a decision file. Same-run path collisions (two slugs resolving to the same path) are noted in preflight as informational, and the later entry wins.
- **`streams[*].body`:** Any markdown is preserved verbatim — `###`, `####` sub-headings, code blocks, lists. The stream title is emitted as `### <title>` under `## What We Did`; stream body follows directly.
- **Preflight is all-or-nothing:** If any preflight check fails, the helper exits with code 2 and no writes occur. Fix the manifest and retry safely. `--only` limits preflight to the active sections only.
- **`marbaji-claude` field:** In YAML, use the key `marbaji-claude` (hyphenated). Both `marbaji-claude` and `marbaji_claude` (underscored) are accepted due to Pydantic's `populate_by_name: True` setting.
- **Shipping Log and Brag Doc insertion order:** New bullets are inserted immediately after the target heading (newest at top of their month/quarter block), not appended at the end.
