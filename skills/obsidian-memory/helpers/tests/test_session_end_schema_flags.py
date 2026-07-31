"""Guards on the self-describing contract flags: --print-schema and --example.

Why: `references/session-end-helper.md` carried 664 lines documenting the same
contract that 18 Pydantic models already enforce, at ~10.8k est. tokens to read on
every session-end, and free to drift from the code. These flags make the code the
authoritative source. The tests below exist so the flags stay usable and, crucially,
so the shipped example cannot rot into something that no longer validates.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HELPER = Path(__file__).resolve().parents[1] / "session_end.py"

sys.path.insert(0, str(HELPER.parent))
import session_end  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_print_schema_emits_valid_json_schema() -> None:
    proc = _run("--print-schema")
    assert proc.returncode == 0, proc.stderr
    schema = json.loads(proc.stdout)
    assert schema.get("title") == "SessionEndManifest"
    assert schema.get("type") == "object"
    # The nested models must be reachable, or the schema is useless as a contract.
    assert "$defs" in schema
    for model in ("ProjectTouched", "Stream", "FilesModified", "FocusUpdates"):
        assert model in schema["$defs"], f"{model} missing from $defs"


def test_print_schema_covers_every_manifest_field() -> None:
    """The generated schema must not silently omit fields the model requires."""
    schema = json.loads(_run("--print-schema").stdout)
    assert set(schema["properties"]) == set(session_end.SessionEndManifest.model_fields)
    expected_required = {
        n for n, f in session_end.SessionEndManifest.model_fields.items() if f.is_required()
    }
    assert set(schema.get("required", [])) == expected_required


def test_print_schema_needs_no_manifest_and_no_vault() -> None:
    """It is a contract dump: it must not touch the filesystem or require setup."""
    proc = _run("--print-schema")
    assert proc.returncode == 0
    assert "error" not in proc.stderr.lower()


def test_example_is_valid_yaml() -> None:
    proc = _run("--example")
    assert proc.returncode == 0, proc.stderr
    assert yaml.safe_load(proc.stdout) is not None


def test_example_actually_validates_against_the_model() -> None:
    """The whole point of shipping an example: it must parse. Guards against rot."""
    raw = yaml.safe_load(_run("--example").stdout)
    session_end.SessionEndManifest.model_validate(raw)


def test_example_contains_every_required_field_and_no_more_than_needed() -> None:
    """Minimal means minimal: all required fields, none of the optional collections."""
    raw = yaml.safe_load(_run("--example").stdout)
    fields = session_end.SessionEndManifest.model_fields
    required = {n for n, f in fields.items() if f.is_required()}
    optional = {n for n, f in fields.items() if not f.is_required()}
    assert required <= set(raw), f"example missing required: {required - set(raw)}"
    assert not (optional & set(raw)), (
        f"example includes optional fields, so it is not minimal: {optional & set(raw)}"
    )


def test_example_topic_satisfies_the_slug_pattern() -> None:
    """A placeholder that violates the model's own pattern would teach the wrong shape."""
    import re

    raw = yaml.safe_load(_run("--example").stdout)
    assert re.match(session_end.SLUG_RE, raw["topic"])
    assert re.match(session_end.SLUG_RE, raw["projects_touched"][0]["slug"])


def test_flags_are_documented_in_help() -> None:
    out = _run("--help").stdout
    assert "--print-schema" in out
    assert "--example" in out


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
