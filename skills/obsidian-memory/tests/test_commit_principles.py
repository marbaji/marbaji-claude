"""commit-principles.sh and principles-autocommit.sh against a local git origin.

Origin: 2026-09-18. The commit step for ~/.claude/work-principles.md depended on a model noticing
a session-end step or a session-start warning; the warning sat at line 167 of a 14.5 KB hook
output and was missed. These scripts now run from hooks, unattended and possibly concurrently, so
they need a lock and a restore guard, and each needs a test that can fail.

`gh` is faked on PATH: `pr create` prints a URL, `pr merge` pushes the worktree's branch to main.
"""
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
COMMIT = SCRIPTS / "commit-principles.sh"
AUTO = SCRIPTS / "principles-autocommit.sh"

FAKE_GH = """#!/bin/bash
# fake gh: `pr create` prints a URL; `pr merge` pushes the current branch to main.
# Every call's argv is appended to $FAKE_GH_CALLS so tests can check the URL and --squash.
# FAKE_GH_MERGE_FAILS=N makes the first N `pr merge` calls fail (GitHub's async-mergeability 405).
[ -n "${FAKE_GH_CALLS:-}" ] && printf '%s\\n' "$*" >> "$FAKE_GH_CALLS"
case "$1 $2" in
  "pr create") echo "https://example.invalid/pr/1" ;;
  "pr merge")
    n=$(grep -c '^pr merge' "${FAKE_GH_CALLS:-/dev/null}" 2>/dev/null || echo 0)
    if [ "$n" -le "${FAKE_GH_MERGE_FAILS:-0}" ]; then echo "GraphQL: Pull request is not mergeable (405)" >&2; exit 1; fi
    git push -q origin "HEAD:main" ;;
  *) echo "fake gh: unsupported $*" >&2; exit 1 ;;
esac
"""


def run(cmd, cwd=None, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if check and r.returncode != 0:
        raise AssertionError(f"{cmd} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


@pytest.fixture
def world(tmp_path):
    """A bare origin, a clone on main holding the principles file, a symlink to it, a fake gh."""
    origin = tmp_path / "origin.git"
    run(["git", "init", "-q", "--bare", "-b", "main", str(origin)])
    clone = tmp_path / "clone"
    run(["git", "clone", "-q", str(origin), str(clone)])
    git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    (clone / "claude-config").mkdir()
    principles = clone / "claude-config" / "work-principles.md"
    principles.write_text("# rules\n\n- rule one\n")
    run(["git", "add", "."], cwd=clone, env=git_env)
    run(["git", "commit", "-q", "-m", "seed"], cwd=clone, env=git_env)
    run(["git", "push", "-q", "-u", "origin", "main"], cwd=clone, env=git_env)
    run(["git", "remote", "set-head", "origin", "main"], cwd=clone, env=git_env)
    link = tmp_path / "work-principles.md"
    link.symlink_to(principles)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    state = tmp_path / "state"
    state.mkdir()
    env = {**git_env, "PATH": f"{bindir}:{os.environ['PATH']}", "PRINCIPLES_FILE": str(link),
           "COMMIT_PRINCIPLES_STATE": str(state), "TMPDIR": str(tmp_path / "tmp"),
           "FAKE_GH_CALLS": str(tmp_path / "gh-calls"), "COMMIT_PRINCIPLES_RETRY_S": "0.05"}
    (tmp_path / "tmp").mkdir()
    return {"origin": origin, "clone": clone, "file": principles, "link": link, "env": env, "state": state}


def origin_main_text(w):
    return run(["git", "show", "origin/main:claude-config/work-principles.md"], cwd=w["clone"], env=w["env"]).stdout


def dirty(w, line="- rule two\n"):
    w["file"].write_text(w["file"].read_text() + line)


def gh_calls(w):
    p = Path(w["env"]["FAKE_GH_CALLS"])
    return p.read_text().splitlines() if p.exists() else []


def test_happy_path_merges_and_leaves_the_file_clean(world):
    dirty(world)
    r = run([str(COMMIT)], env=world["env"])
    assert "merged" in r.stdout, r.stdout
    calls = gh_calls(world)
    assert [c for c in calls if c.startswith("pr create")]
    assert calls[-1] == "pr merge https://example.invalid/pr/1 --squash"   # the URL gh printed, squash-merged
    assert origin_main_text(world) == "# rules\n\n- rule one\n- rule two\n"
    assert world["file"].read_text() == origin_main_text(world)
    status = run(["git", "status", "--porcelain"], cwd=world["clone"], env=world["env"]).stdout
    assert status == ""                       # clean, and main fast-forwarded (no dirty file)
    assert not (world["state"] / "commit-principles.lock").exists()   # lock released


def test_clean_file_is_a_silent_no_op(world):
    r = run([str(COMMIT)], env=world["env"])
    assert r.stdout == "" and r.returncode == 0


def test_lock_held_refuses_and_touches_nothing(world):
    dirty(world)
    (world["state"] / "commit-principles.lock").mkdir()
    r = run([str(COMMIT)], env=world["env"], check=False)
    assert r.returncode != 0
    assert "lock" in r.stdout
    assert origin_main_text(world) == "# rules\n\n- rule one\n"   # nothing pushed
    assert (world["state"] / "commit-principles.lock").exists()    # not ours to remove


def test_stale_lock_is_broken(world):
    dirty(world)
    lock = world["state"] / "commit-principles.lock"
    lock.mkdir()
    old = time.time() - 3600
    os.utime(lock, (old, old))
    r = run([str(COMMIT)], env=world["env"])
    assert "merged" in r.stdout
    assert not lock.exists()


def test_file_edited_mid_run_is_not_overwritten_by_the_restore(world):
    """A session writes a rule while the commit is in flight: the merge carries the earlier text,
    the working file keeps the newer text, and the next run commits it."""
    dirty(world)
    # The fake gh's `pr merge` is the point in the run after the copy and before the restore;
    # this variant also appends a third rule to the working file right there.
    gh = Path(world["env"]["PATH"].split(":")[0]) / "gh"
    gh.write_text(FAKE_GH.replace('git push -q origin "HEAD:main"',
                                  f'git push -q origin "HEAD:main"; printf -- "- rule three\\n" >> "{world["file"]}"'))
    r = run([str(COMMIT)], env=world["env"])
    assert origin_main_text(world) == "# rules\n\n- rule one\n- rule two\n"
    assert world["file"].read_text() == "# rules\n\n- rule one\n- rule two\n- rule three\n"
    assert "changed" in r.stdout            # the message says the restore was skipped
    # and the next run commits the newer text
    gh.write_text(FAKE_GH)
    run([str(COMMIT)], env=world["env"])
    assert origin_main_text(world) == world["file"].read_text()


def test_merge_that_fails_once_is_retried(world):
    """GitHub computes mergeability asynchronously; the first merge can 405."""
    dirty(world)
    r = run([str(COMMIT)], env={**world["env"], "FAKE_GH_MERGE_FAILS": "1"})
    assert "merged" in r.stdout
    assert len([c for c in gh_calls(world) if c.startswith("pr merge")]) == 2
    assert origin_main_text(world) == "# rules\n\n- rule one\n- rule two\n"


def test_merge_that_keeps_failing_leaves_the_pr_open_and_the_file_dirty(world):
    dirty(world)
    env = {**world["env"], "FAKE_GH_MERGE_FAILS": "99"}
    r = run([str(COMMIT)], env=env, check=False)
    assert r.returncode == 1
    assert len([c for c in gh_calls(world) if c.startswith("pr merge")]) == 4      # four attempts, then stop
    assert "stays open" in r.stdout and "405" in r.stdout                         # gh's reason is surfaced
    assert origin_main_text(world) == "# rules\n\n- rule one\n"                # nothing merged
    assert world["file"].read_text().endswith("- rule two\n")                    # the rule stays loaded
    heads = run(["git", "ls-remote", "--heads", "origin"], cwd=world["clone"], env=env).stdout
    assert heads.count("principles/") == 1                                        # the PR's branch stays for a human
    assert not (world["state"] / "commit-principles.lock").exists()               # lock released on the failure path
    # and the next run does not stack a second PR on it
    r2 = run([str(COMMIT)], env=world["env"], check=False)
    assert r2.returncode == 1 and "earlier run left" in r2.stdout


def test_leftover_remote_branch_blocks_a_second_pr(world):
    """An earlier run's merge failed (open PR) or it died after pushing: unattended runs must not
    open a new PR every session boundary on top of it."""
    dirty(world)
    run(["git", "push", "-q", "origin", "main:refs/heads/principles/20260918-000000"], cwd=world["clone"], env=world["env"])
    r = run([str(COMMIT)], env=world["env"], check=False)
    assert r.returncode == 1
    assert "principles/20260918-000000" in r.stdout
    assert origin_main_text(world) == "# rules\n\n- rule one\n"      # nothing new pushed
    heads = run(["git", "ls-remote", "--heads", "origin"], cwd=world["clone"], env=world["env"]).stdout
    assert heads.count("principles/") == 1                               # no second branch


def test_autocommit_is_silent_when_clean(world):
    r = run([str(AUTO)], env={**world["env"], "PRINCIPLES_AUTOCOMMIT_SYNC": "1"})
    assert r.stdout == "" and r.returncode == 0


def test_autocommit_runs_the_commit_when_dirty(world, tmp_path):
    dirty(world)
    log = tmp_path / "log" / "commit-principles.log"
    env = {**world["env"], "PRINCIPLES_AUTOCOMMIT_SYNC": "1", "COMMIT_PRINCIPLES_LOG": str(log)}
    r = run([str(AUTO)], env=env)
    assert "principles" in r.stdout                    # the one-line notice
    assert world["file"].read_text() == origin_main_text(world) == "# rules\n\n- rule one\n- rule two\n"
    assert "merged" in log.read_text()                 # the run was logged, not lost


def test_autocommit_detached_returns_at_once_and_still_commits(world, tmp_path):
    dirty(world)
    # A merge that takes 4 s: a detached launch returns well inside that, a foreground run cannot.
    gh = Path(world["env"]["PATH"].split(":")[0]) / "gh"
    gh.write_text(FAKE_GH.replace('git push -q origin "HEAD:main"', 'sleep 4; git push -q origin "HEAD:main"'))
    log = tmp_path / "log" / "commit-principles.log"
    env = {**world["env"], "COMMIT_PRINCIPLES_LOG": str(log)}
    t0 = time.time()
    r = run([str(AUTO)], env=env)
    assert time.time() - t0 < 3, "the hook side must return before the commit finishes"
    assert r.returncode == 0 and "principles" in r.stdout
    for _ in range(100):                               # the detached run finishes on its own
        if world["file"].read_text() == "# rules\n\n- rule one\n- rule two\n" and \
                run(["git", "status", "--porcelain"], cwd=world["clone"], env=env).stdout == "":
            break
        time.sleep(0.2)
    assert origin_main_text(world) == "# rules\n\n- rule one\n- rule two\n"
    assert "merged" in log.read_text()
