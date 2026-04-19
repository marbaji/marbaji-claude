from __future__ import annotations

from pathlib import Path

import pytest

from ralph_stack import setup as setup_mod
from ralph_stack.paths import ProjectPaths


def test_initresult_fields():
    r = setup_mod.InitResult(
        created=["ralph/"],
        skipped=[],
        upserted={},
        ensured=[],
        next_step="Ready.",
    )
    assert r.created == ["ralph/"]
    assert r.skipped == []
    assert r.upserted == {}
    assert r.ensured == []
    assert r.next_step == "Ready."


def test_initialize_fresh_directory(tmp_path, monkeypatch):
    # Redirect ~/.ralph/ to a tmp location so the test doesn't touch the real HOME
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    paths = ProjectPaths(root=tmp_path / "project")
    paths.root.mkdir()

    result = setup_mod.initialize(paths)

    # Directory effects
    assert (paths.root / "ralph").is_dir()
    assert (paths.root / "tasks" / "lessons.md").is_file()
    assert (paths.root / ".ralphex" / "config").is_file()
    assert (paths.root / ".gitignore").is_file()
    assert (fake_home / ".ralph" / "guardrails.md").is_file()

    # .ralphex/config seeded keys
    cfg = (paths.root / ".ralphex" / "config").read_text()
    assert "claude_command = " in cfg
    assert "use_worktree = true" in cfg
    assert "task_model = opus" in cfg
    assert "plans_dir" not in cfg  # no plan arg given

    # .gitignore seeded entries
    gi = (paths.root / ".gitignore").read_text()
    assert "ralph/" in gi
    assert ".ralphex/*" in gi
    assert "!.ralphex/config" in gi

    # tasks/lessons.md content
    lessons = (paths.root / "tasks" / "lessons.md").read_text()
    assert "# Lessons" in lessons
    assert "Two-tier system" in lessons
    assert "~/.ralph/guardrails.md" in lessons

    # InitResult populated
    assert "ralph/" in result.created
    assert "tasks/lessons.md" in result.created
    assert "ralph-stack run" in result.next_step
