"""Tests for session_end.py helper."""
from datetime import date as Date
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


class TestDecisionFile:
    def _decision(self, **overrides):
        defaults = dict(
            slug="2026-05-09-test-decision",
            title="Test Decision",
            status="accepted",
            owner="[[Work/Chalktalk/People/Mo Arbaji]]",
            stakeholders=["[[Work/Chalktalk/People/Mo Arbaji]]"],
            supersedes=None,
            tags=["decision", "test"],
            context="Why the decision needed making.",
            options_considered=(
                "1. **Option A.** Trade-off: lower complexity.\n"
                "2. **Option B.** Trade-off: more features."
            ),
            chosen="**Option A**",
            reasoning="- Simpler to maintain.",
            consequences="- New constraint X applies.",
        )
        defaults.update(overrides)
        return session_end.Decision(**defaults)

    def test_decision_frontmatter(self):
        decision = self._decision()
        text = session_end.render_decision_file(
            decision,
            source_session_wikilink="[[Sessions/2026-05/2026-05-09-test-session]]",
            session_date=Date(2026, 5, 9),
        )
        assert text.startswith("---\n")
        assert "type: decision\n" in text
        assert "date: 2026-05-09\n" in text
        assert "status: accepted\n" in text
        assert 'owner: "[[Work/Chalktalk/People/Mo Arbaji]]"\n' in text
        assert "stakeholders:\n" in text
        assert '  - "[[Work/Chalktalk/People/Mo Arbaji]]"\n' in text
        assert "supersedes:\n" in text
        assert "tags: [decision, test]\n" in text

    def test_undated_slug_emits_session_date_in_frontmatter(self):
        # Codex adversarial-review finding #2: filename and frontmatter must agree.
        decision = self._decision(slug="undated-foo")
        text = session_end.render_decision_file(
            decision,
            source_session_wikilink="[[Sessions/2026-05/2026-05-09-test-session]]",
            session_date=Date(2026, 5, 9),
        )
        assert "date: 2026-05-09\n" in text

    def test_decision_sections_in_order(self):
        decision = self._decision()
        text = session_end.render_decision_file(
            decision,
            source_session_wikilink="[[Sessions/2026-05/2026-05-09-test-session]]",
            session_date=Date(2026, 5, 9),
        )
        positions = [
            text.index("# Test Decision"),
            text.index("## Context"),
            text.index("## Options Considered"),
            text.index("## Chosen"),
            text.index("## Reasoning"),
            text.index("## Consequences"),
            text.index("## Source Session"),
        ]
        assert positions == sorted(positions)

    def test_undated_slug_inherits_session_date(self):
        decision = self._decision(slug="test-decision")
        path = session_end.decision_file_path(decision, session_date=Date(2026, 5, 9))
        assert path == "Work/Chalktalk/Decisions/2026-05-09-test-decision.md"

    def test_dated_slug_used_directly(self):
        decision = self._decision(slug="2026-05-09-test-decision")
        path = session_end.decision_file_path(decision, session_date=Date(2026, 5, 9))
        assert path == "Work/Chalktalk/Decisions/2026-05-09-test-decision.md"


import shutil


class TestShippingLogAppend:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_append_under_existing_month(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.ShippingEntry(
            date="2026-04-15",
            label="Mid-April thing",
            project_slug="some-project",
            context="quick context",
        )
        session_end.append_to_shipping_log(
            vault=vault,
            entry=entry,
            session_log_filename="2026-04-15-mid-april",
            org_name="Chalktalk",
        )
        log = (vault / "Work/Chalktalk/Shipping Log.md").read_text()
        assert log.index("Mid-April thing") < log.index("Old item shipped earlier")

    def test_creates_new_month_heading_when_missing(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.ShippingEntry(
            date="2026-05-09",
            label="May thing",
            context="May context",
        )
        session_end.append_to_shipping_log(
            vault=vault,
            entry=entry,
            session_log_filename="2026-05-09-may",
            org_name="Chalktalk",
        )
        log = (vault / "Work/Chalktalk/Shipping Log.md").read_text()
        assert "## 2026-05" in log
        assert log.index("## 2026-05") < log.index("## 2026-04")
        assert "May thing" in log

    def test_bullet_format(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.ShippingEntry(
            date="2026-05-09",
            label="May thing",
            context="extra detail",
        )
        session_end.append_to_shipping_log(
            vault=vault,
            entry=entry,
            session_log_filename="2026-05-09-may",
            org_name="Chalktalk",
        )
        log = (vault / "Work/Chalktalk/Shipping Log.md").read_text()
        assert "- **2026-05-09** — May thing — extra detail. [[Sessions/2026-05/2026-05-09-may]]" in log


class TestBragDocAppend:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_create_new_quarter(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.BragEntry(
            quarter="2026 Q2",
            date="2026-05-09",
            body="codified the cross-model review pattern.",
        )
        session_end.append_to_brag_doc(
            vault=vault, entry=entry, session_log_filename="2026-05-09-may",
        )
        log = (vault / "Personal/Brag Doc.md").read_text()
        assert "## 2026 Q2" in log
        assert log.index("## 2026 Q2") < log.index("## 2026 Q1")
        assert "codified the cross-model review pattern." in log

    def test_append_under_existing_quarter(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.BragEntry(
            quarter="2026 Q1",
            date="2026-03-20",
            body="another Q1 brag.",
        )
        session_end.append_to_brag_doc(
            vault=vault, entry=entry, session_log_filename="2026-03-20-thing",
        )
        log = (vault / "Personal/Brag Doc.md").read_text()
        assert log.index("another Q1 brag.") < log.index("old brag entry")

    def test_bullet_format(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.BragEntry(
            quarter="2026 Q2", date="2026-05-09", body="did the thing.",
        )
        session_end.append_to_brag_doc(
            vault=vault, entry=entry, session_log_filename="2026-05-09-test",
        )
        log = (vault / "Personal/Brag Doc.md").read_text()
        assert "- **2026-05-09** — did the thing. [[Sessions/2026-05/2026-05-09-test]]" in log


class TestProjectDocOps:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_append_section_to_existing(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            section_title="Hardening pass",
            section_date="2026-05-09",
            body="Two rounds of review caught 11 bugs.",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = (vault / "Work/Chalktalk/Projects/existing-project.md").read_text()
        assert "## 2026-05-09 — Hardening pass" in text
        assert "Two rounds of review caught 11 bugs." in text
        assert "type: project" in text
        assert "Pre-existing description." in text

    def test_append_to_missing_project_raises(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="nonexistent-project",
            section_title="Whatever",
            section_date="2026-05-09",
            body="Body.",
        )
        with pytest.raises(FileNotFoundError):
            session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")

    def test_write_new_project_doc(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        new_doc = session_end.NewProjectDoc(
            slug="brand-new",
            frontmatter={
                "type": "project",
                "status": "active",
                "started": "2026-05-09",
                "tags": ["project", "work/chalktalk"],
            },
            body="# Brand New\n\n## Overview\nWhat this is.",
        )
        session_end.write_new_project_doc(vault=vault, doc=new_doc, org_name="Chalktalk")
        text = (vault / "Work/Chalktalk/Projects/brand-new.md").read_text()
        assert text.startswith("---\n")
        assert "type: project" in text
        assert "# Brand New" in text

    def test_new_project_doc_collision_raises(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        new_doc = session_end.NewProjectDoc(
            slug="existing-project",
            frontmatter={"type": "project", "status": "active"},
            body="# Existing Project",
        )
        with pytest.raises(FileExistsError):
            session_end.write_new_project_doc(vault=vault, doc=new_doc, org_name="Chalktalk")


class TestCurrentFocusUpdates:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_upsert_new_lands_at_top_of_active(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        updates = session_end.FocusUpdates(
            upsert=[
                session_end.FocusUpsert(
                    slug="brand-new",
                    status_line="**🟡 Brand new project.** Just started.",
                ),
            ],
        )
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = (vault / "Context/current-focus.md").read_text()
        active_section = text.split("## Complete")[0]
        assert active_section.index("brand-new") < active_section.index("foo")
        assert active_section.index("foo") < active_section.index("bar")

    def test_upsert_existing_replaces_status_block(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        updates = session_end.FocusUpdates(
            upsert=[
                session_end.FocusUpsert(
                    slug="foo",
                    status_line="**🔴 Foo is now blocked.** New status.",
                ),
            ],
        )
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = (vault / "Context/current-focus.md").read_text()
        assert "🔴 Foo is now blocked" in text
        assert "Foo is active" not in text

    def test_remove_deletes_heading_and_block(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        updates = session_end.FocusUpdates(remove=["bar"])
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = (vault / "Context/current-focus.md").read_text()
        assert "bar" not in text
        assert "Bar is in progress" not in text

    def test_move_to_complete_adds_checkmark(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        updates = session_end.FocusUpdates(move_to_complete=["foo"])
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = (vault / "Context/current-focus.md").read_text()
        active_section = text.split("## Complete")[0]
        complete_section = text.split("## Complete")[1]
        assert "foo" not in active_section
        assert "[[Work/Chalktalk/Projects/foo]] ✅" in complete_section

    def test_last_updated_frontmatter_bumped(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        session_end.process_focus_updates(
            vault=vault, updates=session_end.FocusUpdates(),
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = (vault / "Context/current-focus.md").read_text()
        assert "last-updated: 2026-05-09-test" in text
        assert "last-updated: 2026-04-30-old-session" not in text
