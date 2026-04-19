from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from ralph_stack.guardrails import has_stale_unverified
from ralph_stack.paths import ProjectPaths
from ralph_stack.report import RunSummary, render_report
from ralph_stack.state import StuckState


def _project_paths() -> ProjectPaths:
    return ProjectPaths(root=Path.cwd())


def cmd_run(plan: str) -> int:
    paths = _project_paths()
    plan_path = Path(plan)
    if not plan_path.exists():
        print(f"error: plan file not found: {plan}", file=sys.stderr)
        return 2
    if has_stale_unverified(paths.per_project_guardrails):
        print("error: stale ⚠️ Unverified rules exist in tasks/lessons.md (>24h old).",
              file=sys.stderr)
        print("Review and promote/edit/delete them before starting a new run.",
              file=sys.stderr)
        return 2

    # Delegate to an orchestration entrypoint. Kept thin so cli remains testable.
    from ralph_stack.orchestrator import run_until_done
    return run_until_done(paths, plan_path)


def cmd_resume() -> int:
    paths = _project_paths()
    if has_stale_unverified(paths.per_project_guardrails):
        print("error: stale ⚠️ Unverified rules in tasks/lessons.md (>24h old). Cannot resume.",
              file=sys.stderr)
        return 2
    if not paths.state_file.exists():
        print("error: no prior run to resume (no stuck-state.json).", file=sys.stderr)
        return 2
    from ralph_stack.orchestrator import resume_run
    return resume_run(paths)


def cmd_status() -> int:
    paths = _project_paths()
    if not paths.state_file.exists():
        print("no run in progress (no stuck-state.json).")
        return 0
    state = StuckState.load(paths.state_file)
    print(f"iteration: {state.current_iteration}")
    print(f"model: {state.current_model}")
    print(f"iterations_since_checkbox: {state.iterations_since_checkbox}")
    print(f"last_escalation_iter: {state.last_escalation_iter}")
    return 0


def cmd_report() -> int:
    paths = _project_paths()
    if not paths.state_file.exists():
        print("no run to report on.", file=sys.stderr)
        return 2
    state = StuckState.load(paths.state_file)
    summary = RunSummary(
        plan_basename="unknown",  # orchestrator persists this in real runs
        date=datetime.now().strftime("%Y-%m-%d"),
        status="RUNNING",
        iterations=state.current_iteration,
    )
    paths.morning_report.write_text(render_report(summary))
    print(f"wrote {paths.morning_report}")
    return 0


def cmd_stop() -> int:
    from ralph_stack.orchestrator import stop_run
    return stop_run(_project_paths())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ralph-stack")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("plan")

    sub.add_parser("resume")
    sub.add_parser("status")
    sub.add_parser("report")
    sub.add_parser("stop")

    args = parser.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args.plan)
    if args.cmd == "resume":
        return cmd_resume()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "report":
        return cmd_report()
    if args.cmd == "stop":
        return cmd_stop()
    return 1


if __name__ == "__main__":
    sys.exit(main())
