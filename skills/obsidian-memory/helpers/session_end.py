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
from datetime import date as Date
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


SLUG_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
DATED_SLUG_RE = r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$"


class ProjectTouched(BaseModel):
    slug: str = Field(pattern=SLUG_RE)
    note: str


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
    why: str


class ProjectDocUpdate(BaseModel):
    slug: str = Field(pattern=SLUG_RE)
    section_title: str
    section_date: Date
    body: str


class NewProjectDoc(BaseModel):
    slug: str = Field(pattern=SLUG_RE)
    frontmatter: dict
    body: str


class FocusUpsert(BaseModel):
    slug: str = Field(pattern=SLUG_RE)
    status_line: str


class FocusUpdates(BaseModel):
    remove: list[str] = Field(default_factory=list)
    upsert: list[FocusUpsert] = Field(default_factory=list)
    move_to_complete: list[str] = Field(default_factory=list)


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
    tags_inline = "[" + ", ".join(manifest.tags) + "]"

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
        lines.append(f"- [[Work/{org_name}/Projects/{proj.slug}]] — {proj.note}")
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
            lines.append(f"- [{src.title}]({src.url}) — {src.why}")
        lines.append("")

    lines.append("## Next Steps")
    lines.append(manifest.next_steps.rstrip())
    lines.append("")

    return "\n".join(lines)


def session_log_path(manifest: SessionEndManifest) -> str:
    """Vault-relative path for the session log."""
    yyyy_mm = manifest.date.strftime("%Y-%m")
    return f"Sessions/{yyyy_mm}/{manifest.date.isoformat()}-{manifest.topic}.md"


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
    tags_inline = "[" + ", ".join(decision.tags) + "]"
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


def append_to_shipping_log(
    vault: Path,
    entry: ShippingEntry,
    session_log_filename: str,
    org_name: str = "Chalktalk",
) -> None:
    """Insert one bullet under the correct ## YYYY-MM heading. Newest at top of month."""
    log_path = vault / f"Work/{org_name}/Shipping Log.md"
    if not log_path.exists():
        raise FileNotFoundError(f"Shipping Log not found at {log_path}")

    bullet = format_shipping_bullet(entry, session_log_filename)
    target_heading = f"## {entry.date.strftime('%Y-%m')}"

    text = log_path.read_text()
    lines = text.splitlines()

    heading_idx = None
    for i, line in enumerate(lines):
        if line.strip() == target_heading:
            heading_idx = i
            break

    if heading_idx is None:
        insert_idx = _find_first_h2(lines)
        new_block = [target_heading, bullet, ""]
        lines = lines[:insert_idx] + new_block + lines[insert_idx:]
    else:
        lines.insert(heading_idx + 1, bullet)

    log_path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""))


def format_brag_bullet(entry: BragEntry, session_log_filename: str) -> str:
    yyyy_mm = entry.date.strftime("%Y-%m")
    sess_link = f"[[Sessions/{yyyy_mm}/{session_log_filename}]]"
    body = entry.body.rstrip(".")
    return f"- **{entry.date.isoformat()}** — {body}. {sess_link}"


def append_to_brag_doc(
    vault: Path,
    entry: BragEntry,
    session_log_filename: str,
) -> None:
    """Insert one bullet under the correct ## YYYY Q<N> heading. Newest at top of quarter."""
    log_path = vault / "Personal/Brag Doc.md"
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

    if heading_idx is None:
        insert_idx = _find_first_h2(lines)
        new_block = [target_heading, bullet, ""]
        lines = lines[:insert_idx] + new_block + lines[insert_idx:]
    else:
        lines.insert(heading_idx + 1, bullet)

    log_path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""))


def append_to_project_doc(
    vault: Path,
    update: ProjectDocUpdate,
    org_name: str = "Chalktalk",
) -> None:
    """Append a dated section to an existing project doc."""
    path = vault / f"Work/{org_name}/Projects/{update.slug}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Project doc not found at {path}. "
            f"Use new_project_docs[] to create it instead of project_doc_updates[]."
        )

    text = path.read_text()
    section = (
        f"\n## {update.section_date.isoformat()} — {update.section_title}\n"
        f"{update.body.rstrip()}\n"
    )
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + section)


def write_new_project_doc(
    vault: Path,
    doc: NewProjectDoc,
    org_name: str = "Chalktalk",
) -> None:
    """Write a brand-new project doc. Fails if file exists."""
    path = vault / f"Work/{org_name}/Projects/{doc.slug}.md"
    if path.exists():
        raise FileExistsError(
            f"Project doc already exists at {path}. "
            f"Use project_doc_updates[] to append, not new_project_docs[]."
        )

    fm_yaml = yaml.safe_dump(doc.frontmatter, default_flow_style=False, sort_keys=False).rstrip()
    text = f"---\n{fm_yaml}\n---\n\n{doc.body.rstrip()}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


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


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point. Returns process exit code."""
    raise NotImplementedError("Wired up in later tasks.")


if __name__ == "__main__":
    sys.exit(main())
