#!/usr/bin/env python3
"""session_end.py -- Render session-end artifacts from a YAML manifest.

Reads a YAML manifest (the agent's structured emit of session-end content),
validates it with Pydantic v2, and writes 8 to 12 markdown artifacts into
the configured Obsidian vault.

See references/session-end-helper.md for the manifest schema.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field as dataclass_field
from datetime import date as Date
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
DATED_SLUG_RE = r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$"
_SLUG_RE_COMPILED = re.compile(SLUG_RE)


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

    work: must match SLUG_RE (kebab-case lowercase).
    personal: any non-empty string; no leading/trailing whitespace, no '/' or newlines.
    """
    if category == "personal":
        if not slug or slug != slug.strip() or "/" in slug or "\n" in slug:
            raise ValueError(
                f"personal slug must be non-empty, no leading/trailing whitespace, "
                f"no '/' or newline characters; got {slug!r}"
            )
    else:
        if not _SLUG_RE_COMPILED.match(slug):
            raise ValueError(
                f"work slug must match {SLUG_RE}; got {slug!r}"
            )
    return slug


def project_doc_path(slug: str, category: str, org_name: str) -> str:
    """Return the vault-relative path for a project doc.

    work:     Work/{org_name}/Projects/{slug}.md
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


class ShippingEntry(BaseModel):
    date: Date
    label: str
    project_slug: Optional[str] = None
    context: Optional[str] = None


class BragEntry(BaseModel):
    quarter: str = Field(pattern=r"^\d{4} Q[1-4]$")
    date: Date
    body: str


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


class FocusUpsert(BaseModel):
    slug: str = Field(pattern=SLUG_RE)
    status_line: str


class FocusUpdates(BaseModel):
    remove: list[str] = Field(default_factory=list)
    upsert: list[FocusUpsert] = Field(default_factory=list)
    move_to_complete: list[str] = Field(default_factory=list)
    priorities: Optional[str] = None  # if set, replaces body of ## Priorities verbatim


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
    """
    if re.match(r"^\d{4}-\d{2}-\d{2}-", decision.slug):
        filename = f"{decision.slug}.md"
    else:
        filename = f"{session_date.isoformat()}-{decision.slug}.md"
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


def format_shipping_bullet(entry: ShippingEntry, session_log_filename: str) -> str:
    """Build the canonical Shipping Log bullet line."""
    yyyy_mm = entry.date.strftime("%Y-%m")
    sess_link = f"[[Sessions/{yyyy_mm}/{session_log_filename}]]"
    if entry.context:
        return f"- **{entry.date.isoformat()}** — {entry.label} — {entry.context}. {sess_link}"
    return f"- **{entry.date.isoformat()}** — {entry.label}. {sess_link}"


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

    # Truncate label for display
    label_display = entry.label[:60] + "..." if len(entry.label) > 60 else entry.label

    if heading_idx is None:
        insert_idx = _find_first_h2(lines)
        new_block = [target_heading, bullet, ""]
        lines = lines[:insert_idx] + new_block + lines[insert_idx:]
        summary_msg = f'## {month_label}: heading created; prepended 1 bullet "{label_display}"'
    else:
        lines.insert(heading_idx + 1, bullet)
        summary_msg = f'## {month_label}: prepended 1 bullet "{label_display}"'

    log_path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""))
    return ChangeReport(path=rel_path, summary=[summary_msg])


def format_brag_bullet(entry: BragEntry, session_log_filename: str) -> str:
    yyyy_mm = entry.date.strftime("%Y-%m")
    sess_link = f"[[Sessions/{yyyy_mm}/{session_log_filename}]]"
    body = entry.body.rstrip(".")
    return f"- **{entry.date.isoformat()}** — {body}. {sess_link}"


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

    # Truncate body for display (matches shipping's rule: 60 chars + "...")
    body_first_line = entry.body.strip().split("\n", 1)[0]
    body_display = (
        body_first_line[:60] + "..." if len(body_first_line) > 60 else body_first_line
    )

    if heading_idx is None:
        insert_idx = _find_first_h2(lines)
        new_block = [target_heading, bullet, ""]
        lines = lines[:insert_idx] + new_block + lines[insert_idx:]
        summary_msg = f'## {entry.quarter}: heading created; prepended 1 entry "{body_display}"'
    else:
        lines.insert(heading_idx + 1, bullet)
        summary_msg = f'## {entry.quarter}: prepended 1 entry "{body_display}"'

    log_path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""))
    return ChangeReport(path=rel_path, summary=[summary_msg])


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

    # 1. Status
    if update.status is not None:
        result = _find_h2_section(lines, _RE_STATUS)
        new_body_lines = [update.status.rstrip(), ""]
        if result is not None:
            heading_idx, body_end = result
            old_count = body_end - (heading_idx + 1)
            new_count = len(new_body_lines)
            lines[heading_idx + 1 : body_end] = new_body_lines
            report_summary.append(f"## Status: replaced ({old_count} to {new_count} lines)")
        else:
            # Append at end
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend([f"## Status", *new_body_lines])
            report_summary.append(f"## Status: created with {len(new_body_lines)} lines")

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
            # Insert new entry right after the heading (and its blank line if present)
            insert_at = heading_idx + 1
            # Skip a single blank line immediately after the heading, if present
            if insert_at < body_end and lines[insert_at].strip() == "":
                insert_at += 1
            lines[insert_at:insert_at] = new_entry_lines

            # Recompute body_end after insertion
            new_body_end = body_end + len(new_entry_lines)

            # Count ### headings in the section
            h3_indices = [
                i for i in range(heading_idx + 1, new_body_end)
                if i < len(lines) and lines[i].startswith("### ")
            ]
            trimmed = 0
            if len(h3_indices) > 3:
                # Drop oldest entries (those lower in the section, beyond index 3)
                # Find the start of the 4th (0-indexed: [3]) h3 entry
                drop_from = h3_indices[3]
                # Find end of section (next ## or end of file)
                drop_to = len(lines)
                for j in range(drop_from, len(lines)):
                    if j != drop_from and lines[j].startswith("## "):
                        drop_to = j
                        break
                trimmed = len(h3_indices) - 3
                del lines[drop_from:drop_to]
            report_summary.append(
                f'## Recent activity: prepended 1 entry "{ra.title}" (trimmed {trimmed} oldest)'
            )
        else:
            # Append new section at end
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend([
                f"## Recent activity",
                "",
                *new_entry_lines,
            ])
            report_summary.append(
                f'## Recent activity: heading created; prepended 1 entry "{ra.title}"'
            )

    # 3. Next Steps
    if update.next_steps is not None:
        result = _find_h2_section(lines, _RE_NEXT_STEPS)
        new_body_lines = [update.next_steps.rstrip(), ""]
        if result is not None:
            heading_idx, body_end = result
            old_count = body_end - (heading_idx + 1)
            new_count = len(new_body_lines)
            lines[heading_idx + 1 : body_end] = new_body_lines
            report_summary.append(f"## Next Steps: replaced ({old_count} to {new_count} lines)")
        else:
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend([f"## Next Steps", *new_body_lines])
            report_summary.append(f"## Next Steps: created with {len(new_body_lines)} lines")

    # 4. Related Sessions
    if update.related_session is not None:
        bullet = f"- {update.related_session}"
        result = _find_h2_section(lines, _RE_RELATED_SESSIONS)
        if result is not None:
            heading_idx, body_end = result
            # Find insertion point: last non-blank line within the section body
            insert_at = body_end
            for j in range(body_end - 1, heading_idx, -1):
                if lines[j].strip() != "":
                    insert_at = j + 1
                    break
            else:
                insert_at = heading_idx + 1
            lines.insert(insert_at, bullet)
            report_summary.append("## Related Sessions: appended 1 wikilink")
        else:
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend([f"## Related Sessions", bullet, ""])
            report_summary.append("## Related Sessions: heading created; appended 1 wikilink")

    # 5. Legacy
    if update.section_title is not None:
        body_lines = update.body.rstrip().splitlines()
        legacy_block = [
            "",
            f"## {update.section_date.isoformat()} — {update.section_title}",
            update.body.rstrip(),
        ]
        lines.extend(legacy_block)
        report_summary.append(
            f"appended section ## {update.section_date.isoformat()} — {update.section_title}"
            f" ({len(body_lines)} lines body)"
        )

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
    a display-name pipe alias.
    """
    prefix = f"### [[Work/{org_name}/Projects/{slug}"
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(prefix) and len(stripped) > len(prefix) and stripped[len(prefix)] in ("]", "|"):
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


def process_focus_updates(
    vault: Path,
    updates: FocusUpdates,
    last_updated_slug: str,
    org_name: str = "Chalktalk",
) -> ChangeReport:
    """Apply remove / upsert / move_to_complete to current-focus.md and bump last-updated."""
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

    # Frontmatter bump (only report when the value actually changed)
    if old_slug != last_updated_slug:
        report_summary.append(f"frontmatter last-updated: {old_slug} to {last_updated_slug}")

    # 1. Removes
    removed_slugs: list[str] = []
    for slug in updates.remove:
        block = _find_entry_block(lines, slug, org_name)
        if block is None:
            continue
        start, end = block
        del lines[start:end]
        removed_slugs.append(slug)
    if removed_slugs:
        report_summary.append(f"removed {len(removed_slugs)}: {removed_slugs}")

    # 2. Move to complete
    moved_slugs: list[str] = []
    for slug in updates.move_to_complete:
        block = _find_entry_block(lines, slug, org_name)
        if block is None:
            continue
        start, end = block
        block_lines = lines[start:end]
        if " ✅" not in block_lines[0]:
            block_lines[0] = block_lines[0].rstrip() + " ✅"
        del lines[start:end]
        complete_idx = _find_section_index(lines, "## Complete")
        if complete_idx is None:
            lines.extend(["", "## Complete", *block_lines])
        else:
            lines[complete_idx + 1 : complete_idx + 1] = block_lines
        moved_slugs.append(slug)
    if moved_slugs:
        report_summary.append(f"## Complete: moved {len(moved_slugs)}: {moved_slugs}")

    # 3. Upsert
    upserted_slugs: list[str] = []
    for upsert in updates.upsert:
        existing = _find_entry_block(lines, upsert.slug, org_name)
        new_block = [
            f"### [[Work/{org_name}/Projects/{upsert.slug}]]",
            upsert.status_line.rstrip(),
            "",
        ]
        if existing is not None:
            start, end = existing
            lines[start:end] = new_block
        else:
            active_idx = _find_section_index(lines, "## Active Projects")
            if active_idx is None:
                lines.extend(["", "## Active Projects", *new_block])
            else:
                lines[active_idx + 1 : active_idx + 1] = ["", *new_block]
        upserted_slugs.append(upsert.slug)
    if upserted_slugs:
        report_summary.append(f"## Active Projects: upserted {len(upserted_slugs)}: {upserted_slugs}")

    # 4. Priorities
    if updates.priorities is not None:
        _RE_PRIORITIES = re.compile(r"^## Priorities\s*$")
        result = _find_h2_section(lines, _RE_PRIORITIES)
        new_prio_lines = updates.priorities.splitlines()
        # Ensure section body ends with a trailing blank line
        if new_prio_lines and new_prio_lines[-1] != "":
            new_prio_lines.append("")
        if result is not None:
            heading_idx, body_end = result
            old_count = body_end - (heading_idx + 1)
            new_count = len(new_prio_lines)
            lines[heading_idx + 1 : body_end] = new_prio_lines
            report_summary.append(f"## Priorities: replaced ({old_count} to {new_count} lines)")
        else:
            # Append section at end of body
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend(["## Priorities", *new_prio_lines])
            report_summary.append(f"## Priorities: created with {len(new_prio_lines)} lines")

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
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--vault-path", type=Path, default=None)
    p.add_argument("--only", type=_comma_list, default=None)
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file change report; only print the trailing summary line.",
    )
    return p


def print_change_report(reports: list[ChangeReport], vault: Path) -> None:
    """Print per-file change blocks. Path is vault-relative.

    Multiple ChangeReport instances that share the same path are merged into a
    single block; their summary lines are concatenated in operation order.
    """
    by_path: dict[str, list[str]] = {}
    for r in reports:
        by_path.setdefault(r.path, []).extend(r.summary)
    for path, summaries in by_path.items():
        print()
        print(path)
        for line in summaries:
            print(f"  {line}")


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
                    f"move_to_complete={list(manifest.focus_updates.move_to_complete)})"
                )
            else:
                rpt = process_focus_updates(
                    vault=vault,
                    updates=manifest.focus_updates,
                    last_updated_slug=manifest.last_updated_slug,
                    org_name=org_name,
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
            print_change_report(change_reports, vault)
        print(f"Wrote session-end artifacts under {vault}.")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point. Returns process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        with args.manifest.open() as f:
            raw = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"error: cannot read manifest: {e}", file=sys.stderr)
        return 1

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
