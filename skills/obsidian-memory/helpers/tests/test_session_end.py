"""Tests for session_end.py helper."""
from pathlib import Path

import pytest

import session_end


class TestManifestValidation:
    def test_missing_required_field_fails(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc:
            session_end.SessionEndManifest.model_validate({"date": "2026-05-09"})

        assert "topic" in str(exc.value)


class TestVaultResolution:
    def test_explicit_arg_wins(self, tmp_path):
        result = session_end.resolve_vault_path(
            arg=tmp_path,
            home=Path("/nonexistent"),
        )
        assert result == tmp_path

    def test_canonical_config_file_used(self, tmp_path):
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        vault = tmp_path / "vault"
        vault.mkdir()
        (home / ".claude" / "obsidian-vault-path").write_text(str(vault) + "\n")

        result = session_end.resolve_vault_path(arg=None, home=home)
        assert result == vault

    def test_legacy_name_fallback(self, tmp_path):
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        (home / "Documents").mkdir(parents=True)
        vault = home / "Documents" / "MyVault"
        vault.mkdir()
        (home / ".claude" / "obsidian-vault-name").write_text("MyVault\n")

        result = session_end.resolve_vault_path(arg=None, home=home)
        assert result == vault

    def test_no_config_returns_none(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        result = session_end.resolve_vault_path(arg=None, home=home)
        assert result is None


class TestSessionLogRender:
    def _minimal_manifest(self):
        return session_end.SessionEndManifest(
            date="2026-05-09",
            topic="test-session",
            tags=["session", "work/chalktalk"],
            last_updated_slug="2026-05-09-test-session",
            summary="One-line summary.",
            projects_touched=[
                session_end.ProjectTouched(slug="foo-bar", note="did stuff"),
            ],
            streams=[
                session_end.Stream(title="Stream 1: Did stuff", body="Body of stream 1."),
            ],
            key_decisions="- Picked option A.",
            learnings="- Learned X.",
            files_modified=session_end.FilesModified(),
            next_steps="- Next: Y.",
        )

    def test_session_log_has_frontmatter(self):
        manifest = self._minimal_manifest()
        text = session_end.render_session_log(manifest, org_name="Chalktalk")
        assert text.startswith("---\n")
        assert "date: 2026-05-09\n" in text
        assert "tags: [session, work/chalktalk]\n" in text

    def test_session_log_has_required_sections(self):
        manifest = self._minimal_manifest()
        text = session_end.render_session_log(manifest, org_name="Chalktalk")
        for header in [
            "# Session: test-session",
            "## Summary",
            "## Projects Touched",
            "## What We Did",
            "## Key Decisions",
            "## Learnings",
            "## Files Created/Modified",
            "## Next Steps",
        ]:
            assert header in text, f"missing: {header!r}"

    def test_projects_touched_uses_org_wikilink(self):
        manifest = self._minimal_manifest()
        text = session_end.render_session_log(manifest, org_name="Chalktalk")
        assert "[[Work/Chalktalk/Projects/foo-bar]] — did stuff" in text

    def test_stream_body_preserved_verbatim(self):
        manifest = self._minimal_manifest()
        text = session_end.render_session_log(manifest, org_name="Chalktalk")
        assert "### Stream 1: Did stuff\nBody of stream 1." in text
