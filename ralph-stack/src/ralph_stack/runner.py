from __future__ import annotations

import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

from ralph_stack.detector import decide, update_state
from ralph_stack.paths import (
    ProjectPaths,
    ensure_global_guardrails,
    global_guardrails_path,
)
from ralph_stack.state import StuckState
from ralph_stack.transcript import Iteration


RALPHEX_CMD = ["ralphex"]  # overridable via env RALPH_STACK_RALPHEX_CMD


def compute_branch_name(plan_path: Path, date: str) -> str:
    return f"ralph/{plan_path.stem}-{date}"


def _ralphex_cmd() -> list[str]:
    override = os.environ.get("RALPH_STACK_RALPHEX_CMD")
    if override:
        return override.split()
    return RALPHEX_CMD


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _upsert_config_key(content: str, key: str, value: str) -> str:
    """Return `content` with `key = value` ensured (existing key replaced, else appended).

    Matches lines of the form ``key = ...`` (preserving any other content).
    """
    lines = content.splitlines() if content else []
    new_line = f"{key} = {value}"
    found = False
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        # Detect `key =` or `key=` at start of logical content (ignore comments).
        if not stripped.startswith("#"):
            # Split on first '=' to check key.
            if "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k == key:
                    out.append(new_line)
                    found = True
                    continue
        out.append(line)
    if not found:
        # Ensure trailing newline separation if file non-empty
        if out and out[-1].strip() != "":
            out.append("")
        out.append(new_line)
    return "\n".join(out) + "\n"


class RalphexRunner:
    """Spawns ralphex, tails its transcript, drives the detector.

    Designed so the tailing/decision loop can be tested with a fake transcript
    source. In production, `transcript_source` reads from ralphex's JSONL file.
    """

    def __init__(
        self,
        paths: ProjectPaths,
        plan_path: Path,
        transcript_source: Callable[[], list[Iteration]],
        on_human_required: Callable[[StuckState, list[Iteration]], None],
    ):
        self.paths = paths
        self.plan_path = plan_path
        self.transcript_source = transcript_source
        self.on_human_required = on_human_required
        self.proc: subprocess.Popen | None = None
        self.all_iters: list[Iteration] = []

    def start(self) -> None:
        self.paths.ensure_dirs()
        ensure_global_guardrails()
        # Write combined guardrails for ralphex to pre-prepend
        self._write_combined_guardrails()
        # Write claude_command override into .ralphex/config (Deviation 2)
        self._write_ralphex_config()
        # Spawn ralphex (Deviation 1: no `run` subcommand; Deviation 3: --worktree)
        self.proc = subprocess.Popen(
            _ralphex_cmd() + ["--worktree", str(self.plan_path)],
            cwd=self.paths.root,
        )

    def _write_combined_guardrails(self) -> None:
        from ralph_stack.guardrails import concat_guardrails
        combined = concat_guardrails(global_guardrails_path(), self.paths.per_project_guardrails)
        (self.paths.ralph_dir / "combined-guardrails.md").write_text(combined)

    def _write_ralphex_config(self) -> None:
        """Upsert `claude_command = <wrapper>` into .ralphex/config.

        Preserves any pre-existing config content. The wrapper script is built
        in Phase 10; we write the line now regardless of whether the script
        exists yet.
        """
        config_dir = self.paths.root / ".ralphex"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config"
        wrapper_path = str(
            (self.paths.root / "scripts" / "claude-ralph-wrapper.sh").resolve()
        )
        existing = config_path.read_text() if config_path.exists() else ""
        updated = _upsert_config_key(existing, "claude_command", wrapper_path)
        config_path.write_text(updated)

    def tick(self, tests_now: dict[str, str]) -> str:
        """Process any new iterations. Return 'running' | 'paused' | 'complete'."""
        state = StuckState.load(self.paths.state_file)
        new_iters = self.transcript_source()
        if not new_iters:
            return "running"

        for it in new_iters:
            self.all_iters.append(it)
            d = decide(state, it, tests_now=tests_now)
            state = update_state(state, it, d, tests_now=tests_now)
            state.save(self.paths.state_file)

            if d.action == "escalate" or d.action == "handback":
                self.paths.model_override.write_text(d.next_model + "\n")
            if d.action == "human_required":
                self._pause()
                self.on_human_required(state, self.all_iters)
                return "paused"

        return "running"

    def _pause(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                os.kill(self.proc.pid, signal.SIGSTOP)
            except ProcessLookupError:
                pass

    def resume(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                os.kill(self.proc.pid, signal.SIGCONT)
            except ProcessLookupError:
                pass

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
