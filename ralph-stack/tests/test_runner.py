from pathlib import Path
from ralph_stack.runner import compute_branch_name


def test_branch_name_from_plan():
    assert compute_branch_name(Path("docs/plans/refactor-renewal-v3.md"), "2026-04-18") \
        == "ralph/refactor-renewal-v3-2026-04-18"


def test_branch_name_strips_extension():
    assert compute_branch_name(Path("my-plan.md"), "2026-04-19") \
        == "ralph/my-plan-2026-04-19"
