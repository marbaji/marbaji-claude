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
    context: str


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
