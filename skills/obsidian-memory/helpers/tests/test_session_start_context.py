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


BUDGET_VARS = ("OBSIDIAN_MEMORY_FOCUS_MAX_BYTES", "OBSIDIAN_MEMORY_BACKLOG_MAX_BYTES")


def _run(
    vault: Path,
    tmp_path: Path,
    cwd: Path | None = None,
    *,
    budgets: dict[str, str] | None = None,
) -> str:
    """Invoke the hook with HOME redirected so it reads our synthetic config.

    Budget env vars are scrubbed from the inherited environment and set only from
    the explicit `budgets` argument. Without this, a developer who happens to
    export OBSIDIAN_MEMORY_FOCUS_MAX_BYTES in their shell would silently exercise
    a different ceiling than the one under test, and the ceiling assertions would
    pass or fail for reasons unrelated to the code. Tests must behave identically
    from a fresh clone on any machine.
    """
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "obsidian-vault-path").write_text(str(vault), encoding="utf-8")
    (home / ".claude" / "obsidian-org-name").write_text("TestOrg", encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if k not in BUDGET_VARS}
    env["HOME"] = str(home)
    env.update(budgets or {})

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


def test_truncation_notice_fires_on_emoji_heavy_content(tmp_path: Path) -> None:
    """Regression: byte-vs-character mismatch silently truncated emoji content.

    The vault marks status with emoji (✅ 🗄️) at 3-4 bytes each. An earlier draft
    cut the output with `head -c` (bytes) but decided whether to print the
    truncation notice with `${#VAR}` (characters). On emoji-heavy input those
    disagree, so output was truncated while the notice stayed silent — defeating
    the ceiling's entire purpose. Every measurement is bytes now.

    This test is built to FAIL against the byte/char-mixing version: the live
    section is sized so its character count lands under the 8000 default while
    its byte count lands over it.
    """
    vault = tmp_path / "EmojiVault"
    (vault / "Context").mkdir(parents=True)
    # Each line is heavy on multi-byte chars, so bytes >> chars.
    line = "### [[p]] ✅ 🗄️ ✅ 🗄️ ✅ 🗄️ status marker padding here\n"
    body = line * 130
    (vault / "Context" / "current-focus.md").write_text(
        f"# Current Focus\n\n## Active Projects\n\n{body}", encoding="utf-8"
    )
    chars = len(f"# Current Focus\n\n## Active Projects\n\n{body}")
    nbytes = len(f"# Current Focus\n\n## Active Projects\n\n{body}".encode("utf-8"))
    assert nbytes > 8000, "fixture must exceed the byte budget"
    assert chars < nbytes, "fixture must have bytes > chars for this to be meaningful"

    out = _run(vault, tmp_path)
    assert "_(truncated at" in out, (
        "content over the BYTE budget was truncated without a notice — "
        "the cut and the comparison are using different units"
    )
    # And the emitted bytes must still be valid UTF-8: a byte-wise cut could
    # otherwise split a multi-byte character mid-sequence.
    out.encode("utf-8").decode("utf-8")


def test_long_backlog_lines_cannot_blow_the_budget(tmp_path: Path) -> None:
    """`head -50` bounds line COUNT, not size. 50 pathological lines must not win.

    Caught in review: the backlog preview was capped at 50 lines with no byte
    ceiling, so a file with 50 very long lines could dominate the whole hook's
    output even though current-focus was properly bounded.
    """
    vault = _make_vault(tmp_path, live_entries=2, archived_entries=0)
    # 40 lines x 2,000 chars = 80,000 chars, well inside the 50-line limit.
    (vault / "Context" / "Project Backlog.md").write_text(
        "".join(f"- backlog item {i} " + ("y" * 2000) + "\n" for i in range(40)),
        encoding="utf-8",
    )
    out = _run(vault, tmp_path)
    assert len(out) <= MAX_OUTPUT_CHARS, (
        f"hook emitted {len(out)} chars; long backlog lines bypassed the ceiling"
    )
    assert "_(truncated" in out


def test_malformed_budget_falls_back_to_default(tmp_path: Path) -> None:
    """A non-numeric budget must warn and use the default, not emit nothing.

    `awk -v max=abc` compares against 0 and drops every line. `set -u` cannot
    catch this because the variable IS set, just nonsense.
    """
    vault = _make_vault(tmp_path, live_entries=3, archived_entries=0)
    # An EMPTY value is not in this list: `${VAR:-8000}` substitutes the default for
    # unset *and* empty, so it never reaches validation and warrants no warning.
    # Covered separately by test_empty_budget_uses_default_silently.
    for bad in ("abc", "0", "-5", "12x", "8000 "):
        home = tmp_path / f"home-{bad.strip() or 'empty'}"
        (home / ".claude").mkdir(parents=True, exist_ok=True)
        (home / ".claude" / "obsidian-vault-path").write_text(str(vault), encoding="utf-8")
        (home / ".claude" / "obsidian-org-name").write_text("TestOrg", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k not in BUDGET_VARS}
        env["HOME"] = str(home)
        env["OBSIDIAN_MEMORY_FOCUS_MAX_BYTES"] = bad
        proc = subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
            check=False,
            timeout=60,
        )
        assert proc.returncode == 0, f"budget={bad!r} exited {proc.returncode}"
        assert "Live Project 0" in proc.stdout, (
            f"budget={bad!r} silently produced no focus content"
        )
        assert "not a positive integer" in proc.stderr or "must be > 0" in proc.stderr


def test_empty_budget_uses_default_silently(tmp_path: Path) -> None:
    """`${VAR:-8000}` treats empty as unset, so no warning and normal output."""
    vault = _make_vault(tmp_path, live_entries=3, archived_entries=0)
    out = _run(vault, tmp_path, budgets={"OBSIDIAN_MEMORY_FOCUS_MAX_BYTES": ""})
    assert "Live Project 0" in out
    assert "_(truncated" not in out


def test_explicit_budget_override_is_honoured(tmp_path: Path) -> None:
    """The knob works, and the tests can drive it deterministically."""
    vault = _make_vault(tmp_path, live_entries=60, archived_entries=0)
    tight = _run(vault, tmp_path, budgets={"OBSIDIAN_MEMORY_FOCUS_MAX_BYTES": "400"})
    loose = _run(vault, tmp_path, budgets={"OBSIDIAN_MEMORY_FOCUS_MAX_BYTES": "20000"})
    assert len(tight) < len(loose)
    assert "_(truncated at ~400 bytes" in tight
    assert "_(truncated at ~20000 bytes" not in loose


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
