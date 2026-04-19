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
