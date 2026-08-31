#!/usr/bin/env python3
"""session_end.py -- Render session-end artifacts from a YAML manifest.

Reads a YAML manifest (the agent's structured emit of session-end content),
validates it with Pydantic v2, and writes 8 to 12 markdown artifacts into
the configured Obsidian vault.

See references/session-end-helper.md for the manifest schema.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field as dataclass_field
from datetime import date as Date, timedelta
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


@dataclass
class ChangeReport:
    """Per-file record of what the helper changed."""
    path: str                          # vault-relative path
    summary: list[str] = dataclass_field(default_factory=list)  # one short string per section/op


SLUG_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
# Work project docs may live in a subfolder of Projects/ (e.g. Work/<org>/Projects/Content/<slug>.md
# after a domain consolidation). A work slug is therefore zero or more folder segments followed by a
# kebab-case file slug. Folder segments allow Title Case and spaces because vault folders commonly use
# them; the final segment stays kebab-case because it becomes a filename.
# Path traversal is impossible: "." is not in the folder-segment character class, so ".." cannot match,
# and the pattern forbids leading, trailing, and doubled separators.
WORK_SLUG_RE = r"^(?:[A-Za-z0-9][A-Za-z0-9 _-]*/)*[a-z0-9]+(?:-[a-z0-9]+)*$"
DATED_SLUG_RE = r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$"
_SLUG_RE_COMPILED = re.compile(SLUG_RE)
_WORK_SLUG_RE_COMPILED = re.compile(WORK_SLUG_RE)

# HTML-looking tag in prose: <noscript>, </div>, <area>, <details class="x">,
# and even path placeholders like <skill-root>. With or without attributes.
_RAW_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(?:\s[^<>`\n]*)?/?>")
_FENCE_SPLIT_RE = re.compile(r"(```.*?```|~~~.*?~~~)", re.S)


def escape_raw_html(text: str) -> str:
    """Backtick-wrap HTML-looking tags so Obsidian renders them literally.

    A bare ``<noscript>`` (or even a placeholder like ``<area>`` from a path
    such as ``.claude/rules/<area>.md``) in note prose makes Obsidian's
    reading view treat everything AFTER it as raw HTML — headings and all
    markdown silently stop rendering for the rest of the note. Root-caused
    2026-06-11 when a session log went un-rendered below its first raw tag.

    Tags already inside inline code spans or fenced code blocks are left
    untouched.
    """
    segments = _FENCE_SPLIT_RE.split(text)
    out: list[str] = []
    for j, seg in enumerate(segments):
        if j % 2 == 1:  # fenced code block — leave verbatim
            out.append(seg)
            continue
        parts = seg.split("`")
        for i in range(0, len(parts), 2):  # even indexes are outside code spans
            parts[i] = _RAW_TAG_RE.sub(lambda m: f"`{m.group(0)}`", parts[i])
        out.append("`".join(parts))
    return "".join(out)


def escape_raw_html_tree(value):
    """Apply escape_raw_html to every string in a nested dict/list structure.

    Run over the raw manifest before validation so EVERY rendered field —
    summary, stream bodies, decision prose, project-doc text, source notes,
    shipping/brag bullets — is protected, including fields added later.
    """
    if isinstance(value, str):
        return escape_raw_html(value)
    if isinstance(value, list):
        return [escape_raw_html_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: escape_raw_html_tree(v) for k, v in value.items()}
    return value


def _dedup_preserve_order(items: list[str]) -> list[str]:
    """Return items deduplicated, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _validate_slug_for_category(slug: str, category: str) -> str:
    """Validate slug based on category.

    work: must match WORK_SLUG_RE - a kebab-case slug, optionally prefixed by folder
          segments (e.g. "Content/curriculum-synthesis-skill" for a project doc that lives
          in Work/<org>/Projects/Content/).
    personal: any non-empty string; no leading/trailing whitespace, no '/' or newlines.
    """
    if category == "personal":
        if not slug or slug != slug.strip() or "/" in slug or "\n" in slug:
            raise ValueError(
                f"personal slug must be non-empty, no leading/trailing whitespace, "
                f"no '/' or newline characters; got {slug!r}"
            )
    else:
        if not _WORK_SLUG_RE_COMPILED.match(slug):
            raise ValueError(
                f"work slug must match {WORK_SLUG_RE} (kebab-case, optionally nested "
                f"under folder segments); got {slug!r}"
            )
    return slug


def project_doc_path(slug: str, category: str, org_name: str) -> str:
    """Return the vault-relative path for a project doc.

    work:     Work/{org_name}/Projects/{slug}.md
              (slug may contain "/" for docs nested under Projects/, e.g. Content/foo)
    personal: Personal/Projects/{slug}/overview.md
    """
    if category == "personal":
        return f"Personal/Projects/{slug}/overview.md"
    return f"Work/{org_name}/Projects/{slug}.md"


class ProjectTouched(BaseModel):
    slug: str
    note: str
    category: Literal["work", "personal"] = "work"

    @model_validator(mode="after")
    def _validate_slug(self) -> "ProjectTouched":
        _validate_slug_for_category(self.slug, self.category)
        return self


class Stream(BaseModel):
    title: str
    body: str


class Decision(BaseModel):
    slug: str = Field(pattern=DATED_SLUG_RE + "|" + SLUG_RE)
    title: str
    category: Literal["work", "personal"] = "work"
    status: str = Field(default="accepted", pattern=r"^(proposed|accepted|superseded|deprecated)$")
    owner: str
    stakeholders: list[str] = Field(default_factory=list)
    supersedes: Optional[str] = None
    tags: list[str] = Field(default_factory=lambda: ["decision"])
    context: str
    options_considered: str
    chosen: str
    reasoning: str
    consequences: str


WIKILINK_RE = re.compile(r"^\[\[([^\[\]\|\n\r]+)(?:\|([^\[\]\|\n\r]+))?\]\]$")


def _validate_wikilinks(value: list[str]) -> list[str]:
    """Reject any entry that is not a bare ``[[target]]`` / ``[[target|alias]]``.

    Both the target and the optional alias must be non-empty, contain no
    embedded brackets, pipes, or newlines, and have no leading or trailing
    whitespace. A single pipe at most. This guards against malformed entries
    that would render as physically split bullets in Shipping Log / Brag Doc.
    """
    def _is_clean(part: str) -> bool:
        return bool(part) and part == part.strip()

    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"see_also entries must be strings; got {type(item).__name__}: {item!r}"
            )
        m = WIKILINK_RE.match(item)
        if m is None or not _is_clean(m.group(1)) or (
            m.group(2) is not None and not _is_clean(m.group(2))
        ):
            raise ValueError(
                f"see_also entries must look like ``[[target]]`` or "
                f"``[[target|alias]]`` with non-empty, non-padded, single-line "
                f"parts and at most one pipe; got {item!r}"
            )
    return value


class ShippingEntry(BaseModel):
    date: Date
    label: str
    project_slug: Optional[str] = None
    context: Optional[str] = None
    see_also: list[str] = Field(default_factory=list)

    @field_validator("see_also")
    @classmethod
    def _check_wikilinks(cls, v: list[str]) -> list[str]:
        return _validate_wikilinks(v)


class BragEntry(BaseModel):
    quarter: str = Field(pattern=r"^\d{4} Q[1-4]$")
    date: Date
    body: str
    see_also: list[str] = Field(default_factory=list)

    @field_validator("see_also")
    @classmethod
    def _check_wikilinks(cls, v: list[str]) -> list[str]:
        return _validate_wikilinks(v)


class NewPersonFlag(BaseModel):
    name: str
    why_flagged: str


class Extractions(BaseModel):
    decisions: list[Decision] = Field(default_factory=list)
    shipping_log: list[ShippingEntry] = Field(default_factory=list)
    brag: list[BragEntry] = Field(default_factory=list)
    new_people: list[NewPersonFlag] = Field(default_factory=list)


class FilesModifiedRepo(BaseModel):
    sha: Optional[str] = None
    pr: Optional[int] = None
    message: str


class FilesModified(BaseModel):
    chalktalk: list[FilesModifiedRepo] = Field(default_factory=list)
    marbaji_claude: list[FilesModifiedRepo] = Field(default_factory=list, alias="marbaji-claude")
    other: dict[str, list[FilesModifiedRepo]] = Field(default_factory=dict)
    local: Optional[str] = None

    model_config = {"populate_by_name": True}


class Source(BaseModel):
    url: str
    title: str
    slug: str = Field(pattern=SLUG_RE)
    type: Literal["article", "github-gist", "video", "documentation", "social-post", "tool"]
    tags: list[str] = Field(default_factory=list)
    summary: str
    takeaways: list[str] = Field(default_factory=list)
    why: str


class RecentActivityEntry(BaseModel):
    date: Date
    title: str
    body: str


class ProjectDocUpdate(BaseModel):
    slug: str
    category: Literal["work", "personal"] = "work"

    # Structured updates (matching prose ritual). All optional.
    status: Optional[str] = None
    recent_activity: Optional[RecentActivityEntry] = None
    next_steps: Optional[str] = None
    related_session: Optional[str] = None

    # `next_steps` overwrites its whole section body. When a project doc carries
    # several threads of work, a manifest written for one thread silently drops
    # the others' items. The helper warns loudly when that would happen; set this
    # to True when the replacement is deliberate, to silence the warning.
    # `status` is deliberately NOT guarded: replacing a current-state line is
    # exactly what that field is for.
    next_steps_replace_ok: bool = False

    # Legacy free-form append (back-compat with existing manifests).
    section_title: Optional[str] = None
    section_date: Optional[Date] = None
    body: Optional[str] = None

    @model_validator(mode="after")
    def _validate_slug_and_fields(self) -> "ProjectDocUpdate":
        _validate_slug_for_category(self.slug, self.category)

        has_structured = any(
            v is not None
            for v in (self.status, self.recent_activity, self.next_steps, self.related_session)
        )
        legacy_fields = (self.section_title, self.section_date, self.body)
        has_any_legacy = any(v is not None for v in legacy_fields)
        has_all_legacy = all(v is not None for v in legacy_fields)

        if has_any_legacy and not has_all_legacy:
            raise ValueError(
                "legacy free-form append requires section_title, section_date, AND body together"
            )

        if not has_structured and not has_all_legacy:
            raise ValueError(
                "ProjectDocUpdate requires at least one update field"
            )

        return self


class NewProjectDoc(BaseModel):
    slug: str
    frontmatter: dict
    body: str
    category: Literal["work", "personal"] = "work"

    @model_validator(mode="after")
    def _validate_slug(self) -> "NewProjectDoc":
        _validate_slug_for_category(self.slug, self.category)
        return self


# --- Staleness tracking for current-focus Active/Backlog projects -----------
# Two cadences (per Mo, 2026-07-04):
#   Active:  due when >= STALE_DAYS since last_worked_on AND any snooze has
#            expired. Question: retire / complete / snooze. There is no
#            separate "keep" — keeping IS a snooze (default SNOOZE_DAYS,
#            any duration on request, e.g. "snooze 3 weeks").
#   Backlog: groomed monthly — every BACKLOG_GROOM_DAYS the question is
#            promote-to-active / keep-in-backlog / retire, where
#            keep-in-backlog is a snooze defaulting to BACKLOG_GROOM_DAYS.
# preflight_validate refuses a manifest that leaves a candidate unaddressed
# (the sweep is code-enforced, not ritual-prose-enforced). Sidecar fields per
# project: last_worked_on (bumped when the project is actually touched),
# last_asked_about (bumped when the sweep asks the user about it), and
# snooze_until (suppression). State lives in a vault-hidden sidecar
# (FOCUS_META_REL); current-focus.md stays clean. The vault sidecar may
# override any of these windows per-vault.
STALE_DAYS = 14
BACKLOG_GROOM_DAYS = 30
SNOOZE_DAYS = 14
FOCUS_META_REL = "Context/.focus-meta.json"


class FocusUpsert(BaseModel):
    slug: str
    status_line: str
    category: Literal["work", "personal"] = "work"

    @model_validator(mode="after")
    def _validate_slug(self) -> "FocusUpsert":
        _validate_slug_for_category(self.slug, self.category)
        return self


class SnoozeOp(BaseModel):
    slug: str
    # None -> per-section default: snooze_days (14) for active projects,
    # backlog_groom_days (30) for backlog ("keep in backlog"). The user can
    # ask for any duration ("snooze 3 weeks" -> days: 21).
    days: Optional[int] = Field(default=None, gt=0)


class FocusUpdates(BaseModel):
    remove: list[str] = Field(default_factory=list)
    upsert: list[FocusUpsert] = Field(default_factory=list)
    move_to_complete: list[str] = Field(default_factory=list)
    move_to_retired: list[str] = Field(default_factory=list)
    # Promote a project from ## Backlog to the top of ## Active Projects,
    # keeping its description block. Stamps last_worked_on (it's current again).
    move_to_active: list[str] = Field(default_factory=list)
    # Entries may be plain slugs (default duration) or {slug, days} mappings.
    snooze: list[SnoozeOp] = Field(default_factory=list)

    @field_validator("snooze", mode="before")
    @classmethod
    def _coerce_snooze(cls, v):
        if isinstance(v, list):
            return [{"slug": item} if isinstance(item, str) else item for item in v]
        return v


# Emitted by `--example`. Kept adjacent to the model it must satisfy, and asserted
# valid by tests, so it cannot rot into an example that no longer parses.
MINIMAL_MANIFEST_EXAMPLE = """
# Minimal valid session-end manifest. Every REQUIRED field is present.
# Optional collections (sources_captured, extractions, project_doc_updates,
# new_project_docs, focus_updates) are omitted; add them as needed.
# Authoritative field contract: `session_end.py --print-schema`.

date: 2026-01-31
topic: short-kebab-case-slug          # must match ^[a-z0-9]+(?:-[a-z0-9]+)*$
tags: [context, active]
last_updated_slug: short-kebab-case-slug
summary: |
  One or two sentences on what this session accomplished.
projects_touched:
  - slug: some-project                # category: personal|work (default work)
    note: What changed for this project.
streams:
  - title: What We Did
    body: |
      Narrative prose for this stream of work.
key_decisions: |
  Decisions made, or "None." if there were none.
learnings: |
  What was learned, or "None." if nothing.
files_modified:
  chalktalk:                          # all four repo keys are optional
    - message: commit or PR subject
      sha: abc1234                    # optional
      pr: 123                         # optional
next_steps: |
  What happens next.
"""


class SessionEndManifest(BaseModel):
    date: Date
    topic: str = Field(pattern=SLUG_RE)
    tags: list[str]
    last_updated_slug: str
    summary: str
    projects_touched: list[ProjectTouched]
    streams: list[Stream]
    key_decisions: str
    learnings: str
    files_modified: FilesModified
    sources_captured: list[Source] = Field(default_factory=list)
    next_steps: str
    extractions: Extractions = Field(default_factory=Extractions)
    project_doc_updates: list[ProjectDocUpdate] = Field(default_factory=list)
    new_project_docs: list[NewProjectDoc] = Field(default_factory=list)
    focus_updates: FocusUpdates = Field(default_factory=FocusUpdates)


def render_session_log(manifest: SessionEndManifest, org_name: str) -> str:
    """Render the full session-log markdown text from the manifest."""
    tags_inline = "[" + ", ".join(_dedup_preserve_order(manifest.tags)) + "]"

    lines: list[str] = [
        "---",
        f"date: {manifest.date.isoformat()}",
        f"tags: {tags_inline}",
        "---",
        "",
        f"# Session: {manifest.topic}",
        "",
        "## Summary",
        manifest.summary.rstrip(),
        "",
        "## Projects Touched",
    ]
    for proj in manifest.projects_touched:
        if proj.category == "personal":
            wikilink = f"[[Personal/Projects/{proj.slug}/overview|{proj.slug}]]"
        else:
            wikilink = f"[[Work/{org_name}/Projects/{proj.slug}]]"
        lines.append(f"- {wikilink} — {proj.note}")
    lines.append("")

    lines.append("## What We Did")
    for stream in manifest.streams:
        lines.append("")
        lines.append(f"### {stream.title}")
        lines.append(stream.body.rstrip())
    lines.append("")

    lines.append("## Key Decisions")
    lines.append(manifest.key_decisions.rstrip())
    lines.append("")

    lines.append("## Learnings")
    lines.append(manifest.learnings.rstrip())
    lines.append("")

    lines.append("## Files Created/Modified")
    fm = manifest.files_modified
    repo_blocks = [
        ("chalktalk", fm.chalktalk),
        ("marbaji-claude", fm.marbaji_claude),
    ]
    for repo_name, items in repo_blocks:
        if items:
            lines.append(f"### {repo_name}")
            for item in items:
                pr_part = f" (PR #{item.pr})" if item.pr else ""
                sha_part = f"`{item.sha}` — " if item.sha else ""
                lines.append(f"- {sha_part}{item.message}{pr_part}")
    for other_repo, items in fm.other.items():
        lines.append(f"### {other_repo}")
        for item in items:
            pr_part = f" (PR #{item.pr})" if item.pr else ""
            sha_part = f"`{item.sha}` — " if item.sha else ""
            lines.append(f"- {sha_part}{item.message}{pr_part}")
    if fm.local:
        lines.append("### local")
        lines.append(fm.local.rstrip())
    lines.append("")

    if manifest.sources_captured:
        lines.append("## Sources Captured")
        for src in manifest.sources_captured:
            link = f"[[Sources/{manifest.date.isoformat()}-{src.slug}|{src.title}]]"
            lines.append(f"- {link} — {src.why}")
        lines.append("")

    lines.append("## Next Steps")
    lines.append(manifest.next_steps.rstrip())
    lines.append("")

    return "\n".join(lines)


def session_log_path(manifest: SessionEndManifest) -> str:
    """Vault-relative path for the session log."""
    yyyy_mm = manifest.date.strftime("%Y-%m")
    return f"Sessions/{yyyy_mm}/{manifest.date.isoformat()}-{manifest.topic}.md"


def render_source_file(source: Source, session_date: Date, session_log_filename: str) -> str:
    """Render the markdown text for a Sources/ file matching the template."""
    yyyy_mm = session_date.strftime("%Y-%m")
    tags_inline = "[" + ", ".join(source.tags) + "]"

    lines: list[str] = [
        "---",
        f"date: {session_date.isoformat()}",
        f"url: {source.url}",
        f"type: {source.type}",
        f"tags: {tags_inline}",
        "---",
        "",
        f"# {source.title}",
        "",
        "## Summary",
        source.summary.rstrip(),
        "",
        "## Takeaways",
    ]
    for takeaway in source.takeaways:
        lines.append(f"- {takeaway}")
    lines.append("")
    lines.append("## Context")
    lines.append(f"Discussed in [[Sessions/{yyyy_mm}/{session_log_filename}]]")
    lines.append(source.why.rstrip())
    lines.append("")

    return "\n".join(lines)


def source_file_path(source: Source, session_date: Date) -> str:
    """Return vault-relative path for a Source file: Sources/YYYY-MM-DD-<slug>.md."""
    return f"Sources/{session_date.isoformat()}-{source.slug}.md"


def write_source_files(
    vault: Path,
    sources: list[Source],
    session_date: Date,
    session_log_filename: str,
) -> list[ChangeReport]:
    """Write each Source file into vault Sources/ directory.

    Skips (with stderr warning) if the file already exists. Does not raise on
    collision, matching the Decision-file behavior.
    """
    reports: list[ChangeReport] = []
    for source in sources:
        rel_path = source_file_path(source, session_date)
        path = vault / rel_path
        if path.exists():
            print(
                f"warning: source file {path} already exists; skipped (no overwrite)",
                file=sys.stderr,
            )
            reports.append(ChangeReport(path=rel_path, summary=["skipped (already exists)"]))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_source_file(source, session_date, session_log_filename))
        reports.append(ChangeReport(path=rel_path, summary=["created"]))
    return reports


def decision_file_path(decision: Decision, session_date: Date, org_name: str = "Chalktalk") -> str:
    """Resolve vault-relative path for a Decision file.

    Slug may be dated (2026-05-09-foo) or undated (foo); undated inherits session_date.

    work:     Work/{org_name}/Decisions/{filename}
    personal: Personal/Decisions/{filename}

    Unlike a personal PROJECT slug (a directory display name, so spaces and Title Case are
    allowed), a decision slug of either category stays kebab-case — it is a filename, and the
    date prefix plus the slug is what makes decisions sort and resolve predictably.
    """
    if re.match(r"^\d{4}-\d{2}-\d{2}-", decision.slug):
        filename = f"{decision.slug}.md"
    else:
        filename = f"{session_date.isoformat()}-{decision.slug}.md"
    if decision.category == "personal":
        return f"Personal/Decisions/{filename}"
    return f"Work/{org_name}/Decisions/{filename}"


def render_decision_file(
    decision: Decision,
    source_session_wikilink: str,
    session_date: Date,
) -> str:
    """Render a single Decision file's markdown text.

    The frontmatter `date:` field is always emitted: from the slug prefix if dated,
    otherwise inheriting from the session date. This keeps filename and frontmatter
    consistent for undated slugs (Codex adversarial-review finding #2, 2026-05-09).
    """
    if m := re.match(r"^(\d{4}-\d{2}-\d{2})-", decision.slug):
        decision_date = m.group(1)
    else:
        decision_date = session_date.isoformat()

    lines: list[str] = [
        "---",
        "type: decision",
        f"date: {decision_date}",
        # Emitted so the work/personal split is carried BY THE NOTE, not only by which
        # folder it happens to sit in. A note that is ever moved keeps its identity, and
        # a consumer can filter on frontmatter instead of relying on a path glob.
        f"category: {decision.category}",
        f"status: {decision.status}",
    ]
    lines.append(f'owner: "{decision.owner}"')
    lines.append("stakeholders:")
    for sh in decision.stakeholders:
        lines.append(f'  - "{sh}"')
    if decision.supersedes:
        lines.append(f'supersedes: "{decision.supersedes}"')
    else:
        lines.append("supersedes:")
    tags_inline = "[" + ", ".join(_dedup_preserve_order(decision.tags)) + "]"
    lines.append(f"tags: {tags_inline}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {decision.title}")
    lines.append("")
    lines.append("## Context")
    lines.append(decision.context.rstrip())
    lines.append("")
    lines.append("## Options Considered")
    lines.append(decision.options_considered.rstrip())
    lines.append("")
    lines.append("## Chosen")
    lines.append(decision.chosen.rstrip())
    lines.append("")
    lines.append("## Reasoning")
    lines.append(decision.reasoning.rstrip())
    lines.append("")
    lines.append("## Consequences")
    lines.append(decision.consequences.rstrip())
    lines.append("")
    lines.append("## Source Session")
    lines.append(f"- {source_session_wikilink}")
    lines.append("")

    return "\n".join(lines)


def _see_also_suffix(see_also: list[str]) -> str:
    """Render `see_also` as ` · See [[link]]` segments in array order. Empty -> ``."""
    return "".join(f" · See {wl}" for wl in see_also)


def format_shipping_bullet(entry: ShippingEntry, session_log_filename: str) -> str:
    """Build the canonical Shipping Log bullet line."""
    yyyy_mm = entry.date.strftime("%Y-%m")
    sess_link = f"[[Sessions/{yyyy_mm}/{session_log_filename}]]"
    suffix = _see_also_suffix(entry.see_also)
    if entry.context:
        return f"- **{entry.date.isoformat()}** — {entry.label} — {entry.context}. {sess_link}{suffix}"
    return f"- **{entry.date.isoformat()}** — {entry.label}. {sess_link}{suffix}"


def _find_first_h2(lines: list[str]) -> int:
    """Return index of first '## ' heading, or end-of-file if none."""
    for i, line in enumerate(lines):
        if line.startswith("## "):
            return i
    return len(lines)


def _find_h2_section(
    lines: list[str], heading_re: re.Pattern[str]
) -> Optional[tuple[int, int]]:
    """Find a section by heading regex. Returns (heading_idx, body_end_idx_exclusive).

    body_end_idx is the index of the next ``## `` heading or len(lines).
    """
    for i, line in enumerate(lines):
        if heading_re.match(line):
            end = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    end = j
                    break
            return (i, end)
    return None


def append_to_shipping_log(
    vault: Path,
    entry: ShippingEntry,
    session_log_filename: str,
    org_name: str = "Chalktalk",
) -> ChangeReport:
    """Insert one bullet under the correct ## YYYY-MM heading. Newest at top of month."""
    rel_path = f"Work/{org_name}/Shipping Log.md"
    log_path = vault / rel_path
    if not log_path.exists():
        raise FileNotFoundError(f"Shipping Log not found at {log_path}")

    bullet = format_shipping_bullet(entry, session_log_filename)
    target_heading = f"## {entry.date.strftime('%Y-%m')}"
    month_label = entry.date.strftime("%Y-%m")

    text = log_path.read_text()
    lines = text.splitlines()

    heading_idx = None
    for i, line in enumerate(lines):
        if line.strip() == target_heading:
            heading_idx = i
            break

    if bullet in lines:
        print(
            f"warning: shipping bullet already present at {log_path}; skipped (idempotent retry)",
            file=sys.stderr,
        )
        return ChangeReport(
            path=rel_path,
            summary=[f"## {month_label}: skipped (bullet already present)"],
        )

    if heading_idx is None:
        insert_idx = _find_first_h2(lines)
        new_block = [target_heading, bullet, ""]
        lines = lines[:insert_idx] + new_block + lines[insert_idx:]
        summary = [
            f"## {month_label}: heading created; prepended 1 bullet",
            f"+ {target_heading}",
            f"+ {bullet}",
        ]
    else:
        lines.insert(heading_idx + 1, bullet)
        summary = [
            f"## {month_label}: prepended 1 bullet",
            f"+ {bullet}",
        ]

    log_path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""))
    return ChangeReport(path=rel_path, summary=summary)


def format_brag_bullet(entry: BragEntry, session_log_filename: str) -> str:
    yyyy_mm = entry.date.strftime("%Y-%m")
    sess_link = f"[[Sessions/{yyyy_mm}/{session_log_filename}]]"
    body = entry.body.rstrip(".")
    suffix = _see_also_suffix(entry.see_also)
    return f"- **{entry.date.isoformat()}** — {body}. {sess_link}{suffix}"


def append_to_brag_doc(
    vault: Path,
    entry: BragEntry,
    session_log_filename: str,
) -> ChangeReport:
    """Insert one bullet under the correct ## YYYY Q<N> heading. Newest at top of quarter."""
    rel_path = "Personal/Brag Doc.md"
    log_path = vault / rel_path
    if not log_path.exists():
        raise FileNotFoundError(f"Brag Doc not found at {log_path}")

    bullet = format_brag_bullet(entry, session_log_filename)
    target_heading = f"## {entry.quarter}"

    text = log_path.read_text()
    lines = text.splitlines()

    heading_idx = None
    for i, line in enumerate(lines):
        if line.strip() == target_heading:
            heading_idx = i
            break

    if bullet in lines:
        print(
            f"warning: brag bullet already present at {log_path}; skipped (idempotent retry)",
            file=sys.stderr,
        )
        return ChangeReport(
            path=rel_path,
            summary=[f"## {entry.quarter}: skipped (bullet already present)"],
        )

    if heading_idx is None:
        insert_idx = _find_first_h2(lines)
        new_block = [target_heading, bullet, ""]
        lines = lines[:insert_idx] + new_block + lines[insert_idx:]
        summary = [
            f"## {entry.quarter}: heading created; prepended 1 entry",
            f"+ {target_heading}",
            f"+ {bullet}",
        ]
    else:
        lines.insert(heading_idx + 1, bullet)
        summary = [
            f"## {entry.quarter}: prepended 1 entry",
            f"+ {bullet}",
        ]

    log_path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""))
    return ChangeReport(path=rel_path, summary=summary)


_RE_STATUS = re.compile(r"^## Status\s*$")
_RE_RECENT = re.compile(r"^## Recent (?:activity|Work)\s*$", re.IGNORECASE)
_RE_NEXT_STEPS = re.compile(r"^## Next [Ss]teps\s*$")
_RE_RELATED_SESSIONS = re.compile(r"^## Related Sessions\s*$")


def append_to_project_doc(
    vault: Path,
    update: ProjectDocUpdate,
    org_name: str = "Chalktalk",
) -> ChangeReport:
    """Apply structured and/or legacy updates to an existing project doc.

    Operations run in deterministic order:
      1. status         -- replace body of ## Status
      2. recent_activity -- prepend entry under ## Recent activity, trim to 3
      3. next_steps     -- replace body of ## Next Steps
      4. related_session -- append bullet to ## Related Sessions
      5. legacy (section_title + section_date + body) -- append ## YYYY-MM-DD — title at end
    """
    rel_path = project_doc_path(update.slug, update.category, org_name)
    path = vault / rel_path
    if not path.exists():
        raise FileNotFoundError(
            f"Project doc not found at {path}. "
            f"Use new_project_docs[] to create it instead of project_doc_updates[]."
        )

    text = path.read_text()
    lines = text.splitlines()
    report_summary: list[str] = []

    def _diff_lines(removed: list[str], added: list[str]) -> list[str]:
        out: list[str] = []
        for ln in removed:
            out.append(f"- {ln}")
        for ln in added:
            out.append(f"+ {ln}")
        return out

    # 1. Status
    if update.status is not None:
        result = _find_h2_section(lines, _RE_STATUS)
        new_body_lines = [update.status.rstrip(), ""]
        if result is not None:
            heading_idx, body_end = result
            old_body = lines[heading_idx + 1 : body_end]
            lines[heading_idx + 1 : body_end] = new_body_lines
            report_summary.append(
                f"## Status: replaced ({len(old_body)} to {len(new_body_lines)} lines)"
            )
            report_summary.extend(_diff_lines(old_body, new_body_lines))
        else:
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend([f"## Status", *new_body_lines])
            report_summary.append(f"## Status: created with {len(new_body_lines)} lines")
            report_summary.extend(_diff_lines([], ["## Status", *new_body_lines]))

    # 2. Recent activity
    if update.recent_activity is not None:
        ra = update.recent_activity
        new_entry_lines = [
            f"### {ra.date.isoformat()} — {ra.title}",
            ra.body.rstrip(),
            "",
        ]
        result = _find_h2_section(lines, _RE_RECENT)
        if result is not None:
            heading_idx, body_end = result
            insert_at = heading_idx + 1
            if insert_at < body_end and lines[insert_at].strip() == "":
                insert_at += 1
            lines[insert_at:insert_at] = new_entry_lines
            new_body_end = body_end + len(new_entry_lines)

            # Count ### headings in the section
            h3_indices = [
                i for i in range(heading_idx + 1, new_body_end)
                if i < len(lines) and lines[i].startswith("### ")
            ]
            trimmed_lines: list[str] = []
            trimmed = 0
            if len(h3_indices) > 3:
                drop_from = h3_indices[3]
                drop_to = len(lines)
                for j in range(drop_from, len(lines)):
                    if j != drop_from and lines[j].startswith("## "):
                        drop_to = j
                        break
                trimmed = len(h3_indices) - 3
                trimmed_lines = lines[drop_from:drop_to]
                del lines[drop_from:drop_to]
            report_summary.append(
                f'## Recent activity: prepended 1 entry "{ra.title}"'
                + (f" (trimmed {trimmed} oldest)" if trimmed else "")
            )
            report_summary.extend(_diff_lines(trimmed_lines, new_entry_lines))
        else:
            if lines and lines[-1] != "":
                lines.append("")
            new_section = [f"## Recent activity", "", *new_entry_lines]
            lines.extend(new_section)
            report_summary.append(
                f'## Recent activity: heading created; prepended 1 entry "{ra.title}"'
            )
            report_summary.extend(_diff_lines([], new_section))

    # 3. Next Steps
    if update.next_steps is not None:
        result = _find_h2_section(lines, _RE_NEXT_STEPS)
        new_body_lines = [update.next_steps.rstrip(), ""]
        if result is not None:
            heading_idx, body_end = result
            old_body = lines[heading_idx + 1 : body_end]
            if not update.next_steps_replace_ok:
                _warn_dropped_lines(
                    update.slug, "next_steps", old_body, update.next_steps
                )
            lines[heading_idx + 1 : body_end] = new_body_lines
            report_summary.append(
                f"## Next Steps: replaced ({len(old_body)} to {len(new_body_lines)} lines)"
            )
            report_summary.extend(_diff_lines(old_body, new_body_lines))
        else:
            if lines and lines[-1] != "":
                lines.append("")
            new_section = [f"## Next Steps", *new_body_lines]
            lines.extend(new_section)
            report_summary.append(f"## Next Steps: created with {len(new_body_lines)} lines")
            report_summary.extend(_diff_lines([], new_section))

    # 4. Related Sessions
    if update.related_session is not None:
        bullet = f"- {update.related_session}"
        result = _find_h2_section(lines, _RE_RELATED_SESSIONS)
        if result is not None:
            heading_idx, body_end = result
            insert_at = body_end
            for j in range(body_end - 1, heading_idx, -1):
                if lines[j].strip() != "":
                    insert_at = j + 1
                    break
            else:
                insert_at = heading_idx + 1
            lines.insert(insert_at, bullet)
            report_summary.append("## Related Sessions: appended 1 wikilink")
            report_summary.extend(_diff_lines([], [bullet]))
        else:
            if lines and lines[-1] != "":
                lines.append("")
            new_section = [f"## Related Sessions", bullet, ""]
            lines.extend(new_section)
            report_summary.append("## Related Sessions: heading created; appended 1 wikilink")
            report_summary.extend(_diff_lines([], new_section))

    # 5. Legacy
    if update.section_title is not None:
        body_lines = update.body.rstrip().splitlines()
        legacy_block = [
            f"## {update.section_date.isoformat()} — {update.section_title}",
            *body_lines,
        ]
        lines.append("")
        lines.extend(legacy_block)
        report_summary.append(
            f"appended section ## {update.section_date.isoformat()} — {update.section_title}"
            f" ({len(body_lines)} lines body)"
        )
        report_summary.extend(_diff_lines([], legacy_block))

    new_text = "\n".join(lines)
    if not new_text.endswith("\n"):
        new_text += "\n"
    path.write_text(new_text)
    return ChangeReport(path=rel_path, summary=report_summary)


def write_new_project_doc(
    vault: Path,
    doc: NewProjectDoc,
    org_name: str = "Chalktalk",
) -> ChangeReport:
    """Write a brand-new project doc. Fails if file exists."""
    rel_path = project_doc_path(doc.slug, doc.category, org_name)
    path = vault / rel_path
    if path.exists():
        raise FileExistsError(
            f"Project doc already exists at {path}. "
            f"Use project_doc_updates[] to append, not new_project_docs[]."
        )

    fm_yaml = yaml.safe_dump(doc.frontmatter, default_flow_style=False, sort_keys=False).rstrip()
    text = f"---\n{fm_yaml}\n---\n\n{doc.body.rstrip()}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return ChangeReport(path=rel_path, summary=["created"])


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split a markdown file into (frontmatter_block_with_delimiters, body)."""
    if not text.startswith("---\n"):
        return "", text
    end_marker = text.find("\n---\n", 4)
    if end_marker == -1:
        return "", text
    fm_end = end_marker + len("\n---\n")
    return text[:fm_end], text[fm_end:]


def _update_last_updated_field(frontmatter: str, slug: str) -> str:
    if "last-updated:" in frontmatter:
        return re.sub(
            r"last-updated:.*$",
            f"last-updated: {slug}",
            frontmatter,
            flags=re.MULTILINE,
        )
    return frontmatter.replace("\n---\n", f"\nlast-updated: {slug}\n---\n", 1)


def _find_entry_block(lines: list[str], slug: str, org_name: str) -> Optional[tuple[int, int]]:
    """Locate (start, end) line indices of an entry's heading + body block.

    The block runs from the heading line until the next ### or ## (exclusive).
    Returns None if not found.

    Matches both plain wikilinks ([[.../slug]]) and aliased wikilinks
    ([[.../slug|Display Name]]) so that upserts correctly replace entries
    written by humans or prose-generated session-end rituals that may include
    a display-name pipe alias. Matches both entry forms for a slug — work
    (``[[Work/<org>/Projects/<slug>]]``) and personal
    (``[[Personal/Projects/<slug>/overview|...]]``) — so remove / move / upsert
    operations, which carry only a slug, work on personal entries too.
    """
    prefixes = (
        f"### [[Work/{org_name}/Projects/{slug}",
        f"### [[Personal/Projects/{slug}/overview",
    )
    for i, line in enumerate(lines):
        stripped = line.strip()
        if any(
            stripped.startswith(prefix)
            and len(stripped) > len(prefix)
            and stripped[len(prefix)] in ("]", "|")
            for prefix in prefixes
        ):
            end = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("### ") or lines[j].startswith("## "):
                    end = j
                    break
            return (i, end)
    return None


def _find_section_index(lines: list[str], heading: str) -> Optional[int]:
    for i, line in enumerate(lines):
        if line.strip() == heading:
            return i
    return None


def _focus_meta_path(vault: Path) -> Path:
    return vault / FOCUS_META_REL


def load_focus_meta(vault: Path) -> dict:
    """Load the per-project staleness sidecar; return a default skeleton if absent."""
    path = _focus_meta_path(vault)
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    data.setdefault("version", 1)
    data.setdefault("stale_days", STALE_DAYS)
    data.setdefault("snooze_days", SNOOZE_DAYS)
    data.setdefault("projects", {})
    return data


def save_focus_meta(vault: Path, meta: dict) -> None:
    """Write the staleness sidecar. Skips writing an empty sidecar that doesn't
    already exist, so runs with no staleness-relevant ops don't litter the vault."""
    path = _focus_meta_path(vault)
    if not meta.get("projects") and not path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def _swept_slugs(vault: Path, org_name: str) -> list[tuple[str, str]]:
    """(slug, section) pairs under '## Active Projects' and '## Backlog'.

    Both sections are swept, on different cadences — active projects for
    staleness (STALE_DAYS), backlog projects for monthly grooming
    (BACKLOG_GROOM_DAYS); a backlogged project quietly rotting is exactly the
    "so I don't forget" case the sweep exists for. Slug is the path segment
    after 'Projects/' for both Work and Personal entries (the same key the
    sidecar uses); section is "active" or "backlog"."""
    path = vault / "Context/current-focus.md"
    if not path.exists():
        return []
    _, body = _split_frontmatter(path.read_text())
    lines = body.splitlines()
    pat = re.compile(r"^###\s+\[\[(?:Work/[^/]+|Personal)/Projects/([^\]|/]+)")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for heading, section in (("## Active Projects", "active"), ("## Backlog", "backlog")):
        start = _find_section_index(lines, heading)
        if start is None:
            continue
        for line in lines[start + 1 :]:
            if line.startswith("## "):
                break
            m = pat.match(line.strip())
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                out.append((m.group(1), section))
    return out


def compute_stale_candidates(
    vault: Path,
    today: Optional[Date] = None,
    org_name: str = "Chalktalk",
    seed_missing: bool = False,
) -> list[dict]:
    """Due Active/Backlog projects, per-section cadence, excluding snoozed ones.

    Active projects are due when >= stale_days (default STALE_DAYS) have passed
    since last_worked_on AND any snooze has expired; backlog projects likewise
    with backlog_groom_days (default BACKLOG_GROOM_DAYS — the monthly grooming
    pass). Returns dicts {slug, section, last_worked_on, last_asked_about,
    days_stale}. A project with no sidecar entry (e.g. added to current-focus
    by hand, outside the helper) is seeded with last_worked_on = today and the
    sidecar saved when seed_missing is True (the --stale-check CLI path);
    otherwise it is skipped, so preflight during --dry-run stays write-free."""
    today = today or Date.today()
    meta = load_focus_meta(vault)
    projects = meta.setdefault("projects", {})
    windows = {
        "active": meta.get("stale_days", STALE_DAYS),
        "backlog": meta.get("backlog_groom_days", BACKLOG_GROOM_DAYS),
    }
    out: list[dict] = []
    seeded = False
    for slug, section in _swept_slugs(vault, org_name):
        entry = projects.get(slug)
        if not entry or not entry.get("last_worked_on"):
            if seed_missing:
                projects.setdefault(slug, {})["last_worked_on"] = today.isoformat()
                seeded = True
            continue
        snooze_until = entry.get("snooze_until")
        if snooze_until:
            try:
                if Date.fromisoformat(snooze_until) > today:
                    continue
            except ValueError:
                pass
        try:
            last = Date.fromisoformat(entry["last_worked_on"])
        except ValueError:
            continue
        days = (today - last).days
        if days >= windows[section]:
            out.append(
                {
                    "slug": slug,
                    "section": section,
                    "last_worked_on": entry["last_worked_on"],
                    "last_asked_about": entry.get("last_asked_about"),
                    "days_stale": days,
                }
            )
    if seeded:
        save_focus_meta(vault, meta)
    return out


def process_focus_updates(
    vault: Path,
    updates: FocusUpdates,
    last_updated_slug: str,
    org_name: str = "Chalktalk",
    today: Optional[Date] = None,
) -> ChangeReport:
    """Apply remove / upsert / move_to_complete / move_to_retired /
    move_to_active / snooze to current-focus.md, update the staleness sidecar,
    and bump last-updated."""
    rel_path = "Context/current-focus.md"
    path = vault / rel_path
    if not path.exists():
        raise FileNotFoundError(f"current-focus.md not found at {path}")

    text = path.read_text()
    frontmatter, body = _split_frontmatter(text)

    # Extract old last-updated value for the report
    old_slug = ""
    m = re.search(r"last-updated:\s*(\S+)", frontmatter)
    if m:
        old_slug = m.group(1)

    frontmatter = _update_last_updated_field(frontmatter, last_updated_slug)

    lines = body.splitlines()
    report_summary: list[str] = []

    def _diff_lines(removed: list[str], added: list[str]) -> list[str]:
        out: list[str] = []
        for ln in removed:
            out.append(f"- {ln}")
        for ln in added:
            out.append(f"+ {ln}")
        return out

    # Frontmatter bump (only report when the value actually changed)
    if old_slug != last_updated_slug:
        report_summary.append(
            f"frontmatter last-updated: {old_slug} to {last_updated_slug}"
        )
        report_summary.extend(
            _diff_lines(
                [f"last-updated: {old_slug}"],
                [f"last-updated: {last_updated_slug}"],
            )
        )

    # 1. Removes
    for slug in updates.remove:
        block = _find_entry_block(lines, slug, org_name)
        if block is None:
            continue
        start, end = block
        removed_block = lines[start:end]
        del lines[start:end]
        report_summary.append(f"removed: {slug}")
        report_summary.extend(_diff_lines(removed_block, []))

    # 2. Move to complete
    for slug in updates.move_to_complete:
        block = _find_entry_block(lines, slug, org_name)
        if block is None:
            continue
        start, end = block
        old_block_lines = list(lines[start:end])
        new_block_lines = list(old_block_lines)
        if " ✅" not in new_block_lines[0]:
            new_block_lines[0] = new_block_lines[0].rstrip() + " ✅"
        del lines[start:end]
        complete_idx = _find_section_index(lines, "## Complete")
        if complete_idx is None:
            lines.extend(["", "## Complete", *new_block_lines])
        else:
            lines[complete_idx + 1 : complete_idx + 1] = new_block_lines
        report_summary.append(f"moved to ## Complete: {slug}")
        report_summary.extend(_diff_lines(old_block_lines, new_block_lines))

    # 2b. Move to retired
    for slug in updates.move_to_retired:
        block = _find_entry_block(lines, slug, org_name)
        if block is None:
            continue
        start, end = block
        old_block_lines = list(lines[start:end])
        new_block_lines = list(old_block_lines)
        if " 🗄️" not in new_block_lines[0]:
            new_block_lines[0] = new_block_lines[0].rstrip() + " 🗄️"
        del lines[start:end]
        retired_idx = _find_section_index(lines, "## Retired Projects")
        if retired_idx is None:
            lines.extend(["", "## Retired Projects", *new_block_lines])
        else:
            lines[retired_idx + 1 : retired_idx + 1] = new_block_lines
        report_summary.append(f"moved to ## Retired Projects: {slug}")
        report_summary.extend(_diff_lines(old_block_lines, new_block_lines))

    # 2c. Move to active (backlog promotion — block moves with its description)
    for slug in updates.move_to_active:
        block = _find_entry_block(lines, slug, org_name)
        if block is None:
            continue
        start, end = block
        block_lines = list(lines[start:end])
        del lines[start:end]
        active_idx = _find_section_index(lines, "## Active Projects")
        if active_idx is None:
            lines.extend(["", "## Active Projects", *block_lines])
        else:
            lines[active_idx + 1 : active_idx + 1] = ["", *block_lines]
        report_summary.append(f"moved to ## Active Projects: {slug}")
        report_summary.extend(_diff_lines([], block_lines))

    # 3. Upsert
    for upsert in updates.upsert:
        existing = _find_entry_block(lines, upsert.slug, org_name)
        if upsert.category == "personal":
            heading = f"### [[Personal/Projects/{upsert.slug}/overview|{upsert.slug}]]"
        else:
            heading = f"### [[Work/{org_name}/Projects/{upsert.slug}]]"
        new_block = [
            heading,
            upsert.status_line.rstrip(),
            "",
        ]
        if existing is not None:
            start, end = existing
            old_block = list(lines[start:end])
            lines[start:end] = new_block
            report_summary.append(f"## Active Projects: upserted {upsert.slug} (replaced existing)")
            report_summary.extend(_diff_lines(old_block, new_block))
        else:
            active_idx = _find_section_index(lines, "## Active Projects")
            if active_idx is None:
                lines.extend(["", "## Active Projects", *new_block])
            else:
                lines[active_idx + 1 : active_idx + 1] = ["", *new_block]
            report_summary.append(f"## Active Projects: upserted {upsert.slug} (new)")
            report_summary.extend(_diff_lines([], new_block))

    # 4. Staleness sidecar (last_worked_on / last_asked_about / snooze / retire)
    day = today or Date.today()
    stamp = day.isoformat()
    meta = load_focus_meta(vault)
    projects = meta["projects"]
    meta_changed = False
    for upsert in updates.upsert:
        entry = projects.setdefault(upsert.slug, {})
        entry["last_worked_on"] = stamp
        entry.pop("snooze_until", None)
        meta_changed = True
    for slug in updates.move_to_active:
        # Promotion makes the project current again: full grace window.
        entry = projects.setdefault(slug, {})
        entry["last_worked_on"] = stamp
        entry["last_asked_about"] = stamp
        entry.pop("snooze_until", None)
        meta_changed = True
    if updates.snooze:
        # A snooze is the record of an ask: stamp last_asked_about (NOT
        # last_worked_on — days-stale keeps accruing honestly). Duration
        # defaults per section: snooze_days for active, backlog_groom_days
        # for "keep in backlog". Sections are read from disk, which still
        # holds the pre-edit file at this point; a snoozed slug is never
        # also moved in the same run.
        sections = dict(_swept_slugs(vault, org_name))
        default_days = {
            "active": meta.get("snooze_days", SNOOZE_DAYS),
            "backlog": meta.get("backlog_groom_days", BACKLOG_GROOM_DAYS),
        }
        for op in updates.snooze:
            entry = projects.setdefault(op.slug, {})
            entry.setdefault("last_worked_on", stamp)
            entry["last_asked_about"] = stamp
            days = op.days or default_days[sections.get(op.slug, "active")]
            entry["snooze_until"] = (day + timedelta(days=days)).isoformat()
            meta_changed = True
    for slug in (*updates.move_to_complete, *updates.move_to_retired, *updates.remove):
        if projects.pop(slug, None) is not None:
            meta_changed = True
    if meta_changed:
        meta["updated"] = stamp
        save_focus_meta(vault, meta)
        report_summary.append(
            f".focus-meta.json: "
            f"{len(updates.upsert) + len(updates.move_to_active)} touched, "
            f"{len(updates.snooze)} snoozed"
        )

    new_body = "\n".join(lines)
    if not new_body.endswith("\n"):
        new_body += "\n"
    path.write_text(frontmatter + new_body)
    return ChangeReport(path=rel_path, summary=report_summary)


def write_decision_files(
    vault: Path,
    decisions: list[Decision],
    session_date: Date,
    session_log_filename: str,
    org_name: str = "Chalktalk",
) -> list[ChangeReport]:
    """Write each Decision file.

    Dedupe and collision detection both key on the resolved output path, not the
    raw slug. Two slugs that map to the same destination (e.g. `foo` and
    `2026-05-09-foo` for a 2026-05-09 session) are reconciled BEFORE any write,
    with the LATER occurrence winning. This prevents input-order-dependent data
    loss (Codex adversarial-review finding #3, 2026-05-09).
    """
    yyyy_mm = session_date.strftime("%Y-%m")
    source_session_link = f"[[Sessions/{yyyy_mm}/{session_log_filename}]]"

    # Canonicalize: dict keyed by resolved path; later entries replace earlier.
    seen: dict[str, Decision] = {}
    for decision in decisions:
        resolved = decision_file_path(decision, session_date, org_name)
        if resolved in seen and seen[resolved].slug != decision.slug:
            print(
                f"warning: decisions {seen[resolved].slug!r} and {decision.slug!r} "
                f"both resolve to {resolved}; later occurrence wins",
                file=sys.stderr,
            )
        elif resolved in seen:
            print(
                f"warning: duplicate decision slug {decision.slug!r} in same run; second wins",
                file=sys.stderr,
            )
        seen[resolved] = decision

    reports: list[ChangeReport] = []
    for resolved, decision in seen.items():
        path = vault / resolved
        if path.exists():
            print(
                f"warning: decision file {path} already exists; skipped (no overwrite)",
                file=sys.stderr,
            )
            reports.append(ChangeReport(path=resolved, summary=["skipped (already exists)"]))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_decision_file(decision, source_session_link, session_date))
        reports.append(ChangeReport(path=resolved, summary=["created"]))
    return reports


def _warn_dropped_lines(
    slug: str, field: str, old_body: list[str], new_body: str
) -> list[str]:
    """Emit a loud stderr warning when a whole-section replace discards content.

    ``next_steps`` overwrites its section body verbatim. When a project doc
    carries several threads of work, a manifest written for one thread silently
    deletes the others' items. This is not blocked, because rewriting a plan
    wholesale is legitimate, but it is made impossible to miss: the dropped
    lines are printed under their own banner rather than buried among the diff
    lines of the change report.

    Returns the dropped lines (for tests); prints nothing when none are lost.

    Origin: 2026-08-30, an InBloom session-end silently dropped three live
    permitting items, noticed only by reading the change report closely.
    """
    replacement = {ln.strip() for ln in new_body.splitlines() if ln.strip()}
    lost = [ln.strip() for ln in old_body if ln.strip() and ln.strip() not in replacement]
    if not lost:
        return []
    print(
        f"\nWARNING: {field!r} on {slug!r} replaced the whole section and dropped "
        f"{len(lost)} existing line(s):",
        file=sys.stderr,
    )
    for ln in lost:
        print(f"  - {ln}", file=sys.stderr)
    print(
        f"  If those belonged to another thread of work, merge them back in. "
        f"Set {field}_replace_ok: true to silence this.\n",
        file=sys.stderr,
    )
    return lost


def preflight_validate(
    manifest: SessionEndManifest,
    vault: Path,
    org_name: str,
    sections: set[str],
) -> list[str]:
    """Walk every target the manifest will touch; return a list of problem strings.

    An empty list means safe to proceed. A non-empty list means abort BEFORE any
    write happens. This guarantees that a partially-completed run cannot leave
    the vault in an inconsistent state on ordinary failures (Codex
    adversarial-review finding #4, 2026-05-09).

    Only checks sections present in `sections` (so `--only` partial runs don't
    fail on issues in skipped sections).
    """
    problems: list[str] = []

    if "project_doc_updates" in sections:
        for upd in manifest.project_doc_updates:
            target = vault / project_doc_path(upd.slug, upd.category, org_name)
            if not target.exists():
                problems.append(
                    f"project_doc_updates: target missing for {upd.category} slug "
                    f"{upd.slug!r} at {target} (use new_project_docs[] instead)"
                )

    if "new_project_docs" in sections:
        for doc in manifest.new_project_docs:
            target = vault / project_doc_path(doc.slug, doc.category, org_name)
            if target.exists():
                problems.append(
                    f"new_project_docs: collision for {doc.category} slug {doc.slug!r} at "
                    f"{target} (use project_doc_updates[] to append, not "
                    f"new_project_docs[])"
                )

    if "extractions" in sections:
        # Decision-file collisions are warned, not blocked (skip-with-warning is
        # the documented behavior). But same-run path collisions (two slugs that
        # map to the same resolved path) are surfaced here so the operator sees
        # them before any write.
        seen_paths: dict[str, str] = {}
        for d in manifest.extractions.decisions:
            resolved = decision_file_path(d, manifest.date, org_name)
            if resolved in seen_paths and seen_paths[resolved] != d.slug:
                problems.append(
                    f"extractions.decisions: slugs {seen_paths[resolved]!r} and "
                    f"{d.slug!r} both resolve to {resolved}; later wins"
                )
            seen_paths[resolved] = d.slug

    if "focus_updates" in sections:
        if not (vault / "Context/current-focus.md").exists():
            problems.append(
                f"focus_updates: vault is missing Context/current-focus.md at "
                f"{vault / 'Context/current-focus.md'}"
            )
        else:
            # Staleness gate: every stale Active/Backlog project must be
            # addressed in this manifest. This is what makes the session-end
            # sweep (session-end.md Step 2b) self-enforcing — a manifest that
            # ignores a stale project fails preflight, forcing the
            # retire/complete/snooze/keep question instead of relying on the
            # ritual prose being followed.
            fu = manifest.focus_updates
            addressed = (
                set(fu.remove)
                | {u.slug for u in fu.upsert}
                | set(fu.move_to_complete)
                | set(fu.move_to_retired)
                | set(fu.move_to_active)
                | {s.slug for s in fu.snooze}
            )
            for cand in compute_stale_candidates(
                vault, today=manifest.date, org_name=org_name
            ):
                if cand["slug"] in addressed:
                    continue
                if cand["section"] == "backlog":
                    problems.append(
                        f"focus_updates: backlog project {cand['slug']!r} is due "
                        f"for monthly grooming ({cand['days_stale']}d since last "
                        f"worked on, {cand['last_worked_on']}). Ask the user "
                        f"promote to active / keep in backlog / retire, then "
                        f"record it via move_to_active[], snooze[] "
                        f"(keep-in-backlog), or move_to_retired[]."
                    )
                else:
                    problems.append(
                        f"focus_updates: stale project {cand['slug']!r} "
                        f"({cand['days_stale']}d since last worked on, "
                        f"{cand['last_worked_on']}) is unaddressed. Ask the "
                        f"user retire / complete / snooze (default 2 weeks, "
                        f"any duration), then record it via move_to_retired[], "
                        f"move_to_complete[], snooze[], or upsert[]."
                    )

    if "extractions" in sections:
        if manifest.extractions.shipping_log:
            shipping_path = vault / f"Work/{org_name}/Shipping Log.md"
            if not shipping_path.exists():
                problems.append(
                    f"extractions.shipping_log: target missing at {shipping_path}"
                )
        if manifest.extractions.brag:
            brag_path = vault / "Personal/Brag Doc.md"
            if not brag_path.exists():
                problems.append(
                    f"extractions.brag: target missing at {brag_path}"
                )

    # Cross-section consistency: warn when projects_touched and project_doc_updates/new_project_docs disagree.
    # These are warnings only -- they do not block the run (not added to problems).
    if "session_log" in sections and (
        "project_doc_updates" in sections or "new_project_docs" in sections
    ):
        touched = {(p.slug, p.category) for p in manifest.projects_touched}
        updated = (
            {(u.slug, u.category) for u in manifest.project_doc_updates}
            | {(d.slug, d.category) for d in manifest.new_project_docs}
        )
        for slug, category in sorted(updated - touched):
            print(
                f"warning: slug {slug!r} ({category}) in project_doc_updates/new_project_docs "
                f"but not in projects_touched; the session log Projects Touched section won't mention it.",
                file=sys.stderr,
            )
        for slug, category in sorted(touched - updated):
            print(
                f"warning: slug {slug!r} ({category}) in projects_touched but no matching "
                f"project_doc_updates or new_project_docs; the session log will reference a project "
                f"that won't be updated.",
                file=sys.stderr,
            )

    return problems


def resolve_vault_path(arg: Optional[Path], home: Path) -> Optional[Path]:
    """Resolve vault path from --vault-path arg, then config files under ~/.claude/.

    Priority:
        1. arg (highest)
        2. ~/.claude/obsidian-vault-path (canonical, post-2026-05)
        3. ~/.claude/obsidian-vault-name + ~/Documents/<name> (legacy fallback)
        4. None (caller exits with code 3)
    """
    if arg is not None:
        return arg

    canonical = home / ".claude" / "obsidian-vault-path"
    if canonical.exists():
        path_str = canonical.read_text().strip()
        if path_str:
            return Path(path_str)

    legacy = home / ".claude" / "obsidian-vault-name"
    if legacy.exists():
        name = legacy.read_text().strip()
        if name:
            return home / "Documents" / name

    return None


VALID_SECTIONS = {
    "session_log", "extractions", "project_doc_updates",
    "new_project_docs", "focus_updates",
}


def _comma_list(value: str) -> list[str]:
    items = [p.strip() for p in value.split(",") if p.strip()]
    invalid = [s for s in items if s not in VALID_SECTIONS]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"unknown section(s): {invalid}. Valid: {sorted(VALID_SECTIONS)}"
        )
    return items


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="session_end.py",
        description=(
            "Render Obsidian-vault session-end artifacts from a YAML manifest. "
            "See references/session-end-helper.md for the manifest schema."
        ),
    )
    p.add_argument("--manifest", required=False, default=None, type=Path)
    p.add_argument(
        "--stale-check",
        action="store_true",
        help=(
            "Print stale Active/Backlog project candidates (JSON) and exit; no "
            "manifest needed. Seeds sidecar entries for projects added to "
            "current-focus outside the helper."
        ),
    )
    p.add_argument(
        "--print-schema",
        action="store_true",
        help=(
            "Print the manifest JSON Schema (generated from the Pydantic models) "
            "and exit. This is the authoritative contract -- prefer it over any "
            "prose field table, which can drift from the models."
        ),
    )
    p.add_argument(
        "--example",
        action="store_true",
        help=(
            "Print a minimal valid manifest (YAML) and exit. Every required field "
            "is present with a placeholder value; optional collections are omitted."
        ),
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--vault-path", type=Path, default=None)
    p.add_argument("--only", type=_comma_list, default=None)
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file change report; only print the trailing summary line.",
    )
    return p


def _section_body_lines(lines: list[str], heading_text: str) -> list[str]:
    """Return the body lines under an H2 heading, exclusive of the heading itself.

    Body runs from heading_idx + 1 until the next ``## `` heading or end of file.
    Lines inside fenced code blocks (``` ... ```) are skipped over when checking
    for the boundary — a ``## `` or ``### `` literal inside a code fence does not
    terminate the section. Returns empty list if heading is not found.
    """
    for i, line in enumerate(lines):
        if line.strip() == heading_text:
            end = len(lines)
            in_fence = False
            for j in range(i + 1, len(lines)):
                ln = lines[j]
                if ln.lstrip().startswith("```"):
                    in_fence = not in_fence
                    continue
                if not in_fence and ln.startswith("## "):
                    end = j
                    break
            return lines[i + 1 : end]
    return []


def _first_stream_block(lines: list[str]) -> list[str]:
    """Return the first ``### <title>`` stream block (heading + body) inside ``## What We Did``.

    Code-fence-aware: a ``### `` literal inside a fenced code block is treated as
    body content, not a stream boundary. NOTE: a genuine nested ``### Subheading``
    inside a stream body (per the helper's contract that ``streams[*].body`` may
    contain nested H3/H4) is structurally indistinguishable from a sibling stream
    and will terminate the preview at that point. The 60-line cap trailer in
    ``_created_file_preview`` provides the overflow signal in either case.

    Empty list if no streams exist.
    """
    body = _section_body_lines(lines, "## What We Did")
    out: list[str] = []
    in_first = False
    in_fence = False
    for ln in body:
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            if in_first:
                out.append(ln)
            continue
        if not in_fence and ln.startswith("### "):
            if in_first:
                break
            in_first = True
            out.append(ln)
            continue
        if in_first:
            out.append(ln)
    return out


def _created_file_preview(vault: Path, rel_path: str, max_lines: int = 60) -> list[str]:
    """Substantive content preview for a newly-created vault file.

    - ``Sessions/.../*.md`` → ``## Summary`` body + first stream block under ``## What We Did``.
    - ``*/Decisions/*.md`` → ``## Chosen`` body + ``## Reasoning`` body (with headings preserved for clarity).
    - Anything else → empty (no preview rule applies).

    Result is capped at ``max_lines``. If the underlying file content is longer, a
    final trailer ``... (<remaining> more lines in file)`` is appended.
    """
    full = vault / rel_path
    if not full.exists():
        return []
    lines = full.read_text().splitlines()

    preview: list[str] = []
    if rel_path.startswith("Sessions/"):
        preview.extend(_section_body_lines(lines, "## Summary"))
        stream_block = _first_stream_block(lines)
        if stream_block:
            if preview and preview[-1] != "":
                preview.append("")
            preview.extend(stream_block)
    elif "/Decisions/" in rel_path:
        chosen = _section_body_lines(lines, "## Chosen")
        reasoning = _section_body_lines(lines, "## Reasoning")
        if chosen:
            preview.append("## Chosen")
            preview.extend(chosen)
        if reasoning:
            if preview and preview[-1] != "":
                preview.append("")
            preview.append("## Reasoning")
            preview.extend(reasoning)
    else:
        return []

    # Trim trailing blank lines so the cap reflects substantive content only.
    while preview and preview[-1] == "":
        preview.pop()

    if len(preview) > max_lines:
        remaining = len(preview) - max_lines
        preview = preview[:max_lines]
        preview.append(f"... ({remaining} more lines in file)")
    return preview


def print_change_report(
    reports: list[ChangeReport],
    vault: Path,
    show_created_preview: bool = True,
) -> None:
    """Print per-file change blocks. Path is vault-relative.

    Multiple ChangeReport instances that share the same path are merged into a
    single block; their summary lines are concatenated in operation order.

    When ``show_created_preview`` is True (default), files whose summary indicates
    a newly-created file (a summary line starting with ``created``) also get a
    ``+ ``-prefixed content preview appended to the block, so the operator can
    visually verify substantive content of newly-created files without opening
    them. Suppressed when ``--quiet`` is passed.
    """
    by_path: dict[str, list[str]] = {}
    for r in reports:
        by_path.setdefault(r.path, []).extend(r.summary)
    for path, summaries in by_path.items():
        print()
        print(path)
        for line in summaries:
            print(f"  {line}")
        if show_created_preview and any(s.startswith("created") for s in summaries):
            preview = _created_file_preview(vault, path)
            for line in preview:
                print(f"  + {line}")


def run(
    manifest: SessionEndManifest,
    vault: Path,
    org_name: str,
    dry_run: bool,
    sections: set[str],
    quiet: bool = False,
) -> int:
    """Orchestrate all writes per the manifest. Returns process exit code.

    Preflight runs first (Codex adversarial-review finding #4): every target the
    active sections will touch is validated, and if anything is wrong (missing
    project doc for an update, collision for a new project doc, etc.) the helper
    aborts with exit 2 BEFORE any write happens. This makes runs all-or-nothing
    in the common-failure case so retries with a fixed manifest don't duplicate
    appends.
    """
    session_log_filename = f"{manifest.date.isoformat()}-{manifest.topic}"

    if dry_run:
        print(f"[dry-run] would render to vault: {vault}")
        print(f"[dry-run] sections to run: {sorted(sections)}")

    # Preflight: surface every problem before mutating the vault.
    problems = preflight_validate(
        manifest=manifest, vault=vault, org_name=org_name, sections=sections,
    )
    if problems:
        print("error: preflight validation failed; no writes performed.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    change_reports: list[ChangeReport] = []

    try:
        if "session_log" in sections:
            if dry_run:
                for src in manifest.sources_captured:
                    rel = source_file_path(src, manifest.date)
                    print(f"[dry-run] would write source: {vault / rel}")
            else:
                source_reports = write_source_files(
                    vault=vault,
                    sources=manifest.sources_captured,
                    session_date=manifest.date,
                    session_log_filename=session_log_filename,
                )
                change_reports.extend(source_reports)
            log_text = render_session_log(manifest, org_name)
            log_path = vault / session_log_path(manifest)
            if dry_run:
                print(f"[dry-run] would write session_log: {log_path} ({len(log_text)} chars)")
            else:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(log_text)
                n_lines = len(log_text.splitlines())
                change_reports.append(
                    ChangeReport(
                        path=session_log_path(manifest),
                        summary=[f"created ({n_lines} lines)"],
                    )
                )

        if "extractions" in sections:
            if manifest.extractions.decisions:
                if dry_run:
                    for d in manifest.extractions.decisions:
                        path = vault / decision_file_path(d, manifest.date, org_name)
                        print(f"[dry-run] would write decision: {path}")
                else:
                    decision_reports = write_decision_files(
                        vault=vault,
                        decisions=manifest.extractions.decisions,
                        session_date=manifest.date,
                        session_log_filename=session_log_filename,
                        org_name=org_name,
                    )
                    change_reports.extend(decision_reports)

            for entry in manifest.extractions.shipping_log:
                if dry_run:
                    print(f"[dry-run] would append shipping bullet: {entry.label}")
                else:
                    rpt = append_to_shipping_log(
                        vault=vault, entry=entry,
                        session_log_filename=session_log_filename,
                        org_name=org_name,
                    )
                    change_reports.append(rpt)

            for entry in manifest.extractions.brag:
                if dry_run:
                    print(f"[dry-run] would append brag bullet: {entry.body[:40]}...")
                else:
                    rpt = append_to_brag_doc(
                        vault=vault, entry=entry,
                        session_log_filename=session_log_filename,
                    )
                    change_reports.append(rpt)

            for person in manifest.extractions.new_people:
                print(f"NEW PERSON FLAG: {person.name} — {person.why_flagged}")
                print("  (Helper does not auto-create People notes; create manually.)")

        if "project_doc_updates" in sections:
            for upd in manifest.project_doc_updates:
                if dry_run:
                    print(f"[dry-run] would append section to project: {upd.slug}")
                else:
                    rpt = append_to_project_doc(vault=vault, update=upd, org_name=org_name)
                    change_reports.append(rpt)

        if "new_project_docs" in sections:
            for doc in manifest.new_project_docs:
                if dry_run:
                    print(f"[dry-run] would create new project: {doc.slug}")
                else:
                    rpt = write_new_project_doc(vault=vault, doc=doc, org_name=org_name)
                    change_reports.append(rpt)

        if "focus_updates" in sections:
            if dry_run:
                upsert_slugs = [u.slug for u in manifest.focus_updates.upsert]
                print(
                    f"[dry-run] would update current-focus.md "
                    f"(remove={list(manifest.focus_updates.remove)}, "
                    f"upsert={upsert_slugs}, "
                    f"move_to_complete={list(manifest.focus_updates.move_to_complete)}, "
                    f"move_to_retired={list(manifest.focus_updates.move_to_retired)}, "
                    f"snooze={list(manifest.focus_updates.snooze)})"
                )
            else:
                rpt = process_focus_updates(
                    vault=vault,
                    updates=manifest.focus_updates,
                    last_updated_slug=manifest.last_updated_slug,
                    org_name=org_name,
                    today=manifest.date,
                )
                change_reports.append(rpt)

    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except FileExistsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not dry_run:
        if not quiet:
            print_change_report(change_reports, vault, show_created_preview=True)
        print(f"Wrote session-end artifacts under {vault}.")
        refresh_qmd_index(quiet=quiet)
    return 0


def refresh_qmd_index(quiet: bool) -> None:
    """Best-effort re-index of the vault so notes just written by this save are
    immediately searchable via `mcp__qmd__query`.

    qmd has no file watcher: it only re-scans when something runs `qmd update`.
    Wiring this into the save ritual is the fix for a real failure — the index
    silently froze for ~7 weeks (288 of 536 docs indexed, lastUpdated stuck at
    2026-05-08) because nothing re-ran `qmd update` after saves, so every note
    added after that date was invisible to semantic search (2026-06).

    `qmd update` re-scans the whole registered collection, so this also picks up
    notes edited directly in Obsidian, not just helper-written ones. `qmd embed`
    only embeds changed chunks, so the steady-state cost is a few seconds.

    Non-fatal by contract: the skill explicitly supports running without qmd, so
    a missing binary or a non-zero exit must never change the save's exit code.
    """
    if shutil.which("qmd") is None:
        return
    for cmd in (["qmd", "update"], ["qmd", "embed"]):
        try:
            subprocess.run(cmd, check=False, capture_output=True, text=True)
        except Exception as e:  # noqa: BLE001 — a reindex failure must not fail the save
            if not quiet:
                print(f"[qmd] skipped '{' '.join(cmd)}': {e}", file=sys.stderr)
            return
    if not quiet:
        print("[qmd] vault index refreshed (update + embed).")


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point. Returns process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    home = Path.home()

    # Self-describing contract. These exist so the manifest schema does not have to
    # be mirrored in prose: `references/session-end-helper.md` used to carry 664
    # table rows of hand-maintained field documentation for the same 18 Pydantic
    # models validated below, which is both ~10.8k est. tokens to read on every
    # session-end and free to drift from the code. The models are the contract.
    if args.print_schema:
        print(
            json.dumps(
                SessionEndManifest.model_json_schema(), indent=2, ensure_ascii=False
            )
        )
        return 0

    if args.example:
        print(MINIMAL_MANIFEST_EXAMPLE.strip())
        return 0

    if args.stale_check:
        vault = resolve_vault_path(args.vault_path, home)
        if vault is None or not vault.exists():
            print(f"error: vault not found. Resolved: {vault}", file=sys.stderr)
            return 3
        org_name_path = home / ".claude" / "obsidian-org-name"
        org_name = (
            org_name_path.read_text().strip() if org_name_path.exists() else "Chalktalk"
        )
        print(
            json.dumps(
                compute_stale_candidates(vault, org_name=org_name, seed_missing=True),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.manifest is None:
        print("error: --manifest is required (or use --stale-check)", file=sys.stderr)
        return 1

    try:
        with args.manifest.open() as f:
            raw = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"error: cannot read manifest: {e}", file=sys.stderr)
        return 1

    # Escape HTML-looking tags in all prose BEFORE validation so every
    # rendered artifact is Obsidian-safe (see escape_raw_html docstring).
    raw = escape_raw_html_tree(raw)

    try:
        manifest = SessionEndManifest.model_validate(raw)
    except Exception as e:
        print(f"error: manifest validation failed: {e}", file=sys.stderr)
        return 1

    home = Path.home()
    vault = resolve_vault_path(args.vault_path, home)
    if vault is None or not vault.exists():
        print(
            f"error: vault not found. Pass --vault-path or write "
            f"~/.claude/obsidian-vault-path. Resolved: {vault}",
            file=sys.stderr,
        )
        return 3

    org_name_path = home / ".claude" / "obsidian-org-name"
    org_name = org_name_path.read_text().strip() if org_name_path.exists() else "Chalktalk"

    sections_to_run = set(args.only) if args.only else set(VALID_SECTIONS)

    return run(
        manifest=manifest,
        vault=vault,
        org_name=org_name,
        dry_run=args.dry_run,
        sections=sections_to_run,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    sys.exit(main())
