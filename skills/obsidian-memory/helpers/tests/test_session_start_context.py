"""Guards on the size and shape of the session-start-context.sh hook output.

Why this file exists: the hook's own header promises "~2K tokens", but an unbounded
`cat` of Context/current-focus.md let it reach 25,173 chars (~6,290 est. tokens) by
2026-07-31 — 3.1x over budget — because that file accumulates completed and retired
projects forever. Prose in a comment did not stop the drift; a failing test will.

These tests build a synthetic vault, so they never read the real one.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "session-start-context.sh"

# The hook's stated budget is ~2K tokens. At the conventional 4 chars/token that is
# ~8,000 chars; allow headroom for a legitimately busy live section and round to 12k.
# If a change pushes past this, either the change is wrong or the budget moved on
# purpose — in which case update this number in the same commit and say why.
MAX_OUTPUT_CHARS = 12_000

ARCHIVE_MARKER = "SHOULD_NOT_BE_INJECTED"


def _make_vault(tmp_path: Path, *, live_entries: int = 5, archived_entries: int = 40) -> Path:
    vault = tmp_path / "TestVault"
    (vault / "Context").mkdir(parents=True)
    (vault / "Sessions").mkdir(parents=True)
    (vault / "Work" / "TestOrg" / "Projects").mkdir(parents=True)

    live = "\n".join(
        f"### [[Work/TestOrg/Projects/live-{i}|Live Project {i}]]\nStatus line for live project {i}.\n"
        for i in range(live_entries)
    )
    # The archive sections are what must never reach stdout. Pad them so that a
    # regression to `cat` blows MAX_OUTPUT_CHARS and fails loudly rather than subtly.
    archived = "\n".join(
        f"### [[Work/TestOrg/Projects/done-{i}|Done Project {i}]] ✅\n"
        f"{ARCHIVE_MARKER} padding for done project {i}. " + ("x" * 400) + "\n"
        for i in range(archived_entries)
    )
    (vault / "Context" / "current-focus.md").write_text(
        "---\ntype: context\n---\n\n# Current Focus\n\n"
        f"## Active Projects\n\n{live}\n\n"
        f"## Complete\n\n{archived}\n\n"
        f"## Retired Projects\n\n### [[old]] 🗄️\n{ARCHIVE_MARKER} retired.\n",
        encoding="utf-8",
    )

    for i in range(3):
        (vault / "Sessions" / f"2026-07-0{i + 1}-session.md").write_text("body", encoding="utf-8")
    for i in range(4):
        (vault / "Work" / "TestOrg" / "Projects" / f"proj-{i}.md").write_text("body", encoding="utf-8")
    return vault


def _run(vault: Path, tmp_path: Path, cwd: Path | None = None) -> str:
    """Invoke the hook with HOME redirected so it reads our synthetic config."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "obsidian-vault-path").write_text(str(vault), encoding="utf-8")
    (home / ".claude" / "obsidian-org-name").write_text("TestOrg", encoding="utf-8")

    env = dict(os.environ, HOME=str(home))
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd or tmp_path),
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, f"hook exited {proc.returncode}: {proc.stderr}"
    return proc.stdout


def test_output_stays_within_budget(tmp_path: Path) -> None:
    """The whole point: a fat archive section must not inflate the injected context."""
    out = _run(_make_vault(tmp_path), tmp_path)
    assert len(out) <= MAX_OUTPUT_CHARS, (
        f"hook emitted {len(out)} chars, over the {MAX_OUTPUT_CHARS} ceiling. "
        "If this is intentional, raise MAX_OUTPUT_CHARS in the same commit and explain why."
    )


def test_archived_sections_are_not_injected(tmp_path: Path) -> None:
    """`## Complete` and `## Retired Projects` stay in the vault, out of context.

    Checks for them as real headings (line-start), not as substrings: the hook's
    footer deliberately names both sections in prose so the reader knows where the
    history went.
    """
    out = _run(_make_vault(tmp_path), tmp_path)
    assert ARCHIVE_MARKER not in out
    headings = [ln for ln in out.splitlines() if ln.startswith("## ")]
    assert "## Complete" not in headings
    assert "## Retired Projects" not in headings
    assert "Done Project 0" not in out


def test_live_sections_are_still_injected(tmp_path: Path) -> None:
    """Positive control — trimming the archive must not trim the part we need."""
    out = _run(_make_vault(tmp_path), tmp_path)
    assert "## Active Projects" in out
    assert "Live Project 0" in out
    assert "Status line for live project 0." in out


def test_focus_ceiling_truncates_a_runaway_live_section(tmp_path: Path) -> None:
    """Backstop: even an all-live file that grows without bound gets capped."""
    vault = _make_vault(tmp_path, live_entries=400, archived_entries=0)
    out = _run(vault, tmp_path)
    assert "_(truncated at" in out
    assert len(out) <= MAX_OUTPUT_CHARS


def test_no_git_section(tmp_path: Path) -> None:
    """Claude Code's own gitStatus block already carries this; a third copy is waste."""
    vault = _make_vault(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    git = shutil.which("git")
    if git is None:  # pragma: no cover - git is present in CI and locally
        pytest.skip("git not available")
    for args in (["init", "-q"], ["config", "user.email", "t@t.t"], ["config", "user.name", "t"]):
        subprocess.run([git, "-C", str(repo), *args], check=True, capture_output=True)
    (repo / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run([git, "-C", str(repo), "add", "f.txt"], check=True, capture_output=True)
    subprocess.run(
        [git, "-C", str(repo), "commit", "-qm", "UNIQUE_COMMIT_SUBJECT"],
        check=True,
        capture_output=True,
    )

    out = _run(vault, tmp_path, cwd=repo)
    assert "### Git:" not in out
    assert "UNIQUE_COMMIT_SUBJECT" not in out
    assert "Recent commits:" not in out


def test_unconfigured_vault_is_a_silent_noop(tmp_path: Path) -> None:
    """Never block session start on a machine that hasn't set the skill up."""
    home = tmp_path / "bare-home"
    (home / ".claude").mkdir(parents=True)
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=dict(os.environ, HOME=str(home)),
        cwd=str(tmp_path),
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_missing_vault_path_does_not_block(tmp_path: Path) -> None:
    """A renamed or absent vault warns on stderr and exits clean."""
    home = tmp_path / "home2"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "obsidian-vault-path").write_text(str(tmp_path / "nope"), encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=dict(os.environ, HOME=str(home)),
        cwd=str(tmp_path),
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    assert "not found" in proc.stderr


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
