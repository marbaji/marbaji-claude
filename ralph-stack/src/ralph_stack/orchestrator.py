from __future__ import annotations

from pathlib import Path

from ralph_stack.paths import ProjectPaths


def run_until_done(paths: ProjectPaths, plan_path: Path) -> int:
    raise NotImplementedError("filled in during Phase 9")


def resume_run(paths: ProjectPaths) -> int:
    raise NotImplementedError("filled in during Phase 9")


def stop_run(paths: ProjectPaths) -> int:
    raise NotImplementedError("filled in during Phase 9")
