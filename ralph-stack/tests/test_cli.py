from pathlib import Path

from ralph_stack.cli import main


def test_status_no_state(tmp_project: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_project)
    rc = main(["status"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "no run in progress" in captured.out.lower()


def test_resume_blocks_on_stale_unverified(tmp_project: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_project)
    # Seed stale unverified rules
    lessons = tmp_project / "tasks" / "lessons.md"
    lessons.parent.mkdir()
    lessons.write_text("# Lessons\n\n## ⚠️ Unverified (2026-04-01)\n- stale draft\n")
    rc = main(["resume"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "unverified" in captured.err.lower()
