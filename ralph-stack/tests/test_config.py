from __future__ import annotations

from pathlib import Path

from ralph_stack import config


def test_wrapper_path_is_absolute():
    p = config.wrapper_path()
    assert p.is_absolute()


def test_wrapper_path_ends_with_wrapper_script():
    p = config.wrapper_path()
    assert p.name == "claude-ralph-wrapper.sh"
    assert p.parent.name == "scripts"


def test_wrapper_path_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p1 = config.wrapper_path()
    monkeypatch.chdir(tmp_path.parent)
    p2 = config.wrapper_path()
    assert p1 == p2


def test_wrapper_path_points_at_real_file():
    # The wrapper script ships with the package.
    assert config.wrapper_path().exists()
