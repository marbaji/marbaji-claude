from __future__ import annotations

import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from ralph_stack.escalation import draft_guardrail_rules, write_stuck_dump
from ralph_stack.guardrails import append_draft_rules
from ralph_stack.paths import ProjectPaths
from ralph_stack.report import RunSummary, render_report
from ralph_stack.runner import RalphexRunner, compute_branch_name
from ralph_stack.state import StuckState
from ralph_stack.transcript_source import ClaudeCodeStreamJsonSource


def _find_ralphex_transcript_dir(paths: ProjectPaths) -> Path:
    """Return the directory ralphex's Claude sessions write into.

    Each ralphex iteration is a fresh Claude Code session that writes one
    JSONL file into ``~/.claude/projects/<hashed-cwd>/``. Per Spike Deviation A,
    we track the DIRECTORY and let
    :class:`ClaudeCodeStreamJsonSource` emit one ``Iteration`` per new file.

    The directory is overridable via ``RALPH_STACK_TRANSCRIPT_DIR``. Otherwise
    we pick the newest-mtime subdirectory under ``~/.claude/projects/``.
    """
    env = os.environ.get("RALPH_STACK_TRANSCRIPT_DIR")
    if env:
        return Path(env)
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        raise FileNotFoundError(
            f"No Claude Code projects dir at {base}; "
            "set RALPH_STACK_TRANSCRIPT_DIR to the per-project session directory."
        )
    candidates = sorted(
        (p for p in base.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "Could not locate a ralphex session directory; "
        "set RALPH_STACK_TRANSCRIPT_DIR."
    )


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _on_human_required(paths: ProjectPaths, state: StuckState, all_iters) -> None:
    write_stuck_dump(paths.stuck_dump, all_iters, paused_at=state.current_iteration)
    existing = ""
    if paths.per_project_guardrails.exists():
        existing = paths.per_project_guardrails.read_text()
    rules = draft_guardrail_rules(paths.stuck_dump, existing)
    if rules:
        append_draft_rules(paths.per_project_guardrails, date=_today(), rules=rules)
    _write_paused_report(paths, state, unverified=rules)


def _write_paused_report(paths: ProjectPaths, state: StuckState, unverified: list) -> None:
    summary = RunSummary(
        plan_basename=os.environ.get("RALPH_STACK_PLAN_BASENAME", "unknown"),
        date=_today(),
        status="PAUSED",
        paused_at_iter=state.current_iteration,
        iterations=state.current_iteration,
        unverified_rules=unverified or [],
    )
    paths.morning_report.write_text(render_report(summary))


def run_until_done(paths: ProjectPaths, plan_path: Path) -> int:
    paths.ensure_dirs()

    # Deviation B: ralphex owns the worktree (via its `--worktree` flag);
    # ralph-stack no longer does `git checkout -B` here.

    os.environ["RALPH_STACK_PLAN_BASENAME"] = plan_path.stem

    transcript_dir = _find_ralphex_transcript_dir(paths)
    source = ClaudeCodeStreamJsonSource(transcript_dir)

    runner = RalphexRunner(
        paths=paths,
        plan_path=plan_path,
        transcript_source=source.read_new,
        on_human_required=lambda state, iters: _on_human_required(paths, state, iters),
    )
    runner.start()

    try:
        while True:
            time.sleep(5)
            status = runner.tick(tests_now={})
            if status == "paused":
                print(
                    f"PAUSED at iter {StuckState.load(paths.state_file).current_iteration}. "
                    f"See {paths.morning_report}"
                )
                return 0
            if runner.proc and runner.proc.poll() is not None:
                # ralphex exited on its own → run complete
                _write_complete_report(paths, plan_path)
                return 0
    except KeyboardInterrupt:
        runner.stop()
        return 130


def _write_complete_report(paths: ProjectPaths, plan_path: Path) -> None:
    state = StuckState.load(paths.state_file) if paths.state_file.exists() else StuckState()
    summary = RunSummary(
        plan_basename=plan_path.stem,
        date=_today(),
        status="COMPLETE",
        iterations=state.current_iteration,
        branch=compute_branch_name(plan_path, _today()),
    )
    paths.morning_report.write_text(render_report(summary))


def resume_run(paths: ProjectPaths) -> int:
    # Resume = relaunch ralphex; it reads the plan fresh and flips remaining checkboxes.
    # The state file persists the detector's understanding so signals carry over.
    plan_env = os.environ.get("RALPH_STACK_PLAN_PATH")
    if not plan_env:
        print("error: set RALPH_STACK_PLAN_PATH to the plan you were running.", file=sys.stderr)
        return 2
    return run_until_done(paths, Path(plan_env))


def stop_run(paths: ProjectPaths) -> int:
    pid_file = paths.ralph_dir / "ralphex.pid"
    if not pid_file.exists():
        print("no running ralphex process tracked.")
        return 0
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
    except (ValueError, ProcessLookupError):
        pass
    return 0
