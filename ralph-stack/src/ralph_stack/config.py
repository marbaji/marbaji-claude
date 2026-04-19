from __future__ import annotations

from pathlib import Path


def wrapper_path() -> Path:
    """Return the absolute path to scripts/claude-ralph-wrapper.sh inside the
    installed ralph-stack package.

    Computed from __file__ so it works regardless of the user's CWD or whether
    ralph-stack was installed via pip editable or standard install.
    """
    return (Path(__file__).parent.parent.parent / "scripts" / "claude-ralph-wrapper.sh").resolve()
