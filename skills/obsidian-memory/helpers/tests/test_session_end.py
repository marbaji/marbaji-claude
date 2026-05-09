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

    def test_upsert_existing_with_pipe_alias_replaces_block(self, tmp_path):
        """Upsert must replace entries whose heading uses a display-name alias.

        When current-focus.md has an entry written by a prose ritual or human
        that includes a pipe alias (e.g. ``### [[Work/Chalktalk/Projects/foo|Foo Alias]]``),
        upsert should still detect and replace it, not insert a duplicate.
        """
        vault = self._setup_vault(tmp_path)
        focus_path = vault / "Context/current-focus.md"
        # Patch the fixture: replace the plain [[.../foo]] heading with an aliased one.
        text = focus_path.read_text()
        text = text.replace(
            "### [[Work/Chalktalk/Projects/foo]]",
            "### [[Work/Chalktalk/Projects/foo|Foo Alias Display Name]]",
        )
        focus_path.write_text(text)

        updates = session_end.FocusUpdates(
            upsert=[
                session_end.FocusUpsert(
                    slug="foo",
                    status_line="**🔴 Foo is now blocked after alias test.** Updated.",
                ),
            ],
        )
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        result = focus_path.read_text()
        # The old aliased heading must be gone.
        assert "Foo Alias Display Name" not in result
        # The old status must be gone.
        assert "Foo is active" not in result
        # The new status is present exactly once.
        assert result.count("Foo is now blocked after alias test") == 1

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


class TestDecisionExtraction:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_writes_decision_file(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        decision = session_end.Decision(
            slug="2026-05-09-foo",
            title="Foo Decision",
            owner="[[Work/Chalktalk/People/Mo Arbaji]]",
            stakeholders=["[[Work/Chalktalk/People/Mo Arbaji]]"],
            tags=["decision"],
            context="Why.",
            options_considered="1. A.\n2. B.",
            chosen="**A**",
            reasoning="- Clearer.",
            consequences="- Implies X.",
        )
        session_end.write_decision_files(
            vault=vault,
            decisions=[decision],
            session_date=Date(2026, 5, 9),
            session_log_filename="2026-05-09-test",
            org_name="Chalktalk",
        )
        path = vault / "Work/Chalktalk/Decisions/2026-05-09-foo.md"
        assert path.exists()
        text = path.read_text()
        assert "type: decision" in text
        assert "[[Sessions/2026-05/2026-05-09-test]]" in text

    def test_existing_file_skipped_with_warning(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        existing = vault / "Work/Chalktalk/Decisions/2026-05-09-foo.md"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("---\nexisting: true\n---\n")
        decision = session_end.Decision(
            slug="2026-05-09-foo",
            title="Foo Decision",
            owner="[[Work/Chalktalk/People/Mo Arbaji]]",
            tags=["decision"],
            context="x",
            options_considered="x",
            chosen="x",
            reasoning="x",
            consequences="x",
        )
        session_end.write_decision_files(
            vault=vault,
            decisions=[decision],
            session_date=Date(2026, 5, 9),
            session_log_filename="2026-05-09-test",
            org_name="Chalktalk",
        )
        assert existing.read_text() == "---\nexisting: true\n---\n"
        captured = capsys.readouterr()
        assert "skipped" in captured.err.lower() or "exists" in captured.err.lower()

    def test_duplicate_slug_in_same_run_second_wins_with_warning(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        d1 = session_end.Decision(
            slug="2026-05-09-foo", title="First", owner="x", tags=["decision"],
            context="x", options_considered="x", chosen="x", reasoning="x", consequences="x",
        )
        d2 = session_end.Decision(
            slug="2026-05-09-foo", title="Second", owner="x", tags=["decision"],
            context="x", options_considered="x", chosen="x", reasoning="x", consequences="x",
        )
        session_end.write_decision_files(
            vault=vault, decisions=[d1, d2],
            session_date=Date(2026, 5, 9),
            session_log_filename="2026-05-09-test", org_name="Chalktalk",
        )
        text = (vault / "Work/Chalktalk/Decisions/2026-05-09-foo.md").read_text()
        assert "# Second" in text
        captured = capsys.readouterr()
        assert "duplicate" in captured.err.lower() or "second" in captured.err.lower()

    def test_dated_and_undated_slugs_resolving_same_path_reconcile(self, tmp_path, capsys):
        # Codex adversarial-review finding #3: dedupe must canonicalize on resolved path.
        # `foo` and `2026-05-09-foo` both resolve to 2026-05-09-foo.md; the LATER one wins
        # before any write happens, not after a stale "file exists" skip on the second.
        vault = self._setup_vault(tmp_path)
        d_undated = session_end.Decision(
            slug="foo", title="Undated", owner="x", tags=["decision"],
            context="x", options_considered="x", chosen="x", reasoning="x", consequences="x",
        )
        d_dated = session_end.Decision(
            slug="2026-05-09-foo", title="Dated Wins", owner="x", tags=["decision"],
            context="x", options_considered="x", chosen="x", reasoning="x", consequences="x",
        )
        session_end.write_decision_files(
            vault=vault, decisions=[d_undated, d_dated],
            session_date=Date(2026, 5, 9),
            session_log_filename="2026-05-09-test", org_name="Chalktalk",
        )
        text = (vault / "Work/Chalktalk/Decisions/2026-05-09-foo.md").read_text()
        # Later entry (d_dated, "Dated Wins") survives, regardless of slug form
        assert "# Dated Wins" in text
        assert "# Undated" not in text
        captured = capsys.readouterr()
        assert "resolve" in captured.err.lower()


class TestPreflightValidation:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_preflight_passes_clean_manifest(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest = session_end.SessionEndManifest(
            date="2026-05-09",
            topic="ok",
            tags=["session"],
            last_updated_slug="2026-05-09-ok",
            summary="x",
            projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
        )
        problems = session_end.preflight_validate(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            sections={"session_log", "extractions", "project_doc_updates",
                      "new_project_docs", "focus_updates"},
        )
        assert problems == []

    def test_preflight_flags_missing_project_doc_for_update(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest = session_end.SessionEndManifest(
            date="2026-05-09", topic="ok", tags=["session"],
            last_updated_slug="x", summary="x", projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x", learnings="x",
            files_modified=session_end.FilesModified(), next_steps="x",
            project_doc_updates=[
                session_end.ProjectDocUpdate(
                    slug="does-not-exist",
                    section_title="x", section_date="2026-05-09", body="x",
                ),
            ],
        )
        problems = session_end.preflight_validate(
            manifest=manifest, vault=vault, org_name="Chalktalk",
            sections={"project_doc_updates"},
        )
        assert any("does-not-exist" in p for p in problems)

    def test_preflight_flags_collision_for_new_project_doc(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest = session_end.SessionEndManifest(
            date="2026-05-09", topic="ok", tags=["session"],
            last_updated_slug="x", summary="x", projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x", learnings="x",
            files_modified=session_end.FilesModified(), next_steps="x",
            new_project_docs=[
                session_end.NewProjectDoc(
                    slug="existing-project",  # already exists in fixture vault
                    frontmatter={"type": "project", "status": "active"},
                    body="x",
                ),
            ],
        )
        problems = session_end.preflight_validate(
            manifest=manifest, vault=vault, org_name="Chalktalk",
            sections={"new_project_docs"},
        )
        assert any("existing-project" in p for p in problems)

    def test_preflight_only_checks_active_sections(self, tmp_path):
        # If a section is excluded via --only, its problems should be ignored.
        vault = self._setup_vault(tmp_path)
        manifest = session_end.SessionEndManifest(
            date="2026-05-09", topic="ok", tags=["session"],
            last_updated_slug="x", summary="x", projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x", learnings="x",
            files_modified=session_end.FilesModified(), next_steps="x",
            project_doc_updates=[
                session_end.ProjectDocUpdate(
                    slug="does-not-exist",
                    section_title="x", section_date="2026-05-09", body="x",
                ),
            ],
        )
        problems = session_end.preflight_validate(
            manifest=manifest, vault=vault, org_name="Chalktalk",
            sections={"session_log"},  # project_doc_updates NOT included
        )
        assert problems == []


class TestEndToEnd:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_full_run_writes_all_artifacts(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
        ])
        assert rc == 0

        session_log = vault / "Sessions/2026-05/2026-05-09-full-example.md"
        assert session_log.exists()
        log_text = session_log.read_text()
        assert "## Summary" in log_text
        assert "Body of stream 1." in log_text

        decision = vault / "Work/Chalktalk/Decisions/2026-05-09-test-decision.md"
        assert decision.exists()
        assert "type: decision" in decision.read_text()

        shipping = (vault / "Work/Chalktalk/Shipping Log.md").read_text()
        assert "shipped thing" in shipping

        brag = (vault / "Personal/Brag Doc.md").read_text()
        assert "did the thing" in brag

        proj = (vault / "Work/Chalktalk/Projects/existing-project.md").read_text()
        assert "## 2026-05-09 — Today's work" in proj
        # Structured update also landed
        assert "End-to-end test updated status." in proj
        assert "Full manifest test run" in proj
        assert "Verify PR passes CI." in proj
        assert "2026-05-09-full-example]] — full manifest e2e" in proj

        focus = (vault / "Context/current-focus.md").read_text()
        assert "🟢 Existing project active." in focus
        assert "last-updated: 2026-05-09-full-example" in focus
        assert "1. Ship the helper" in focus
        assert "2. Finish e2e coverage" in focus
        assert "3. Phase 2 ritual rewrite" not in focus  # old priorities replaced


class TestPartialRun:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_only_extractions_skips_session_log(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
            "--only", "extractions",
        ])
        assert rc == 0
        assert not (vault / "Sessions/2026-05/2026-05-09-full-example.md").exists()
        focus = (vault / "Context/current-focus.md").read_text()
        assert "🟢 Existing project active." not in focus
        assert (vault / "Work/Chalktalk/Decisions/2026-05-09-test-decision.md").exists()

    def test_only_session_log_focus_skips_extractions(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
            "--only", "session_log,focus_updates",
        ])
        assert rc == 0
        assert (vault / "Sessions/2026-05/2026-05-09-full-example.md").exists()
        focus = (vault / "Context/current-focus.md").read_text()
        assert "🟢 Existing project active." in focus
        assert not (vault / "Work/Chalktalk/Decisions/2026-05-09-test-decision.md").exists()


class TestDryRun:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_dry_run_writes_nothing(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
            "--dry-run",
        ])
        assert rc == 0
        assert not (vault / "Sessions/2026-05/2026-05-09-full-example.md").exists()
        assert not (vault / "Work/Chalktalk/Decisions/2026-05-09-test-decision.md").exists()

        focus_before = (Path(__file__).parent / "fixtures" / "vault" / "Context" / "current-focus.md").read_text()
        focus_after = (vault / "Context/current-focus.md").read_text()
        assert focus_before == focus_after

        captured = capsys.readouterr()
        for needle in ["session_log", "decision", "shipping", "brag", "project", "current-focus"]:
            assert needle in captured.out.lower(), f"dry-run preview missing: {needle}"


class TestEdgeCases:
    def _setup_vault(self, tmp_path, vault_subdir="vault"):
        vault = tmp_path / vault_subdir
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_vault_path_with_spaces(self, tmp_path):
        vault = self._setup_vault(tmp_path, vault_subdir="My Vault With Spaces")
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_minimal.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
        ])
        assert rc == 0
        assert (vault / "Sessions/2026-05/2026-05-09-minimal.md").exists()

    def test_frontmatter_preserved_in_shipping_log(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        before = (vault / "Work/Chalktalk/Shipping Log.md").read_text()
        before_fm = before.split("---\n", 2)[1]

        manifest_path = tmp_path / "m.yaml"
        manifest_path.write_text("""
date: 2026-05-09
topic: fm-test
tags: [session]
last_updated_slug: x
summary: x
projects_touched: []
streams: [{title: x, body: x}]
key_decisions: x
learnings: x
files_modified: {}
next_steps: x
extractions:
  shipping_log:
    - date: 2026-05-09
      label: thing
      context: ctx
""")
        rc = session_end.main([
            "--manifest", str(manifest_path),
            "--vault-path", str(vault),
            "--only", "extractions",
        ])
        assert rc == 0
        after = (vault / "Work/Chalktalk/Shipping Log.md").read_text()
        after_fm = after.split("---\n", 2)[1]
        assert before_fm == after_fm

    def test_empty_extractions_lists_no_op(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_minimal.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
        ])
        assert rc == 0
        log = (vault / "Work/Chalktalk/Shipping Log.md").read_text()
        assert "minimal" not in log
        assert not list((vault / "Work/Chalktalk/Decisions").glob("2026-05-09-*"))


class TestCLI:
    VALID_SECTIONS = {
        "session_log", "extractions", "project_doc_updates",
        "new_project_docs", "focus_updates",
    }

    def test_parse_only_valid_sections(self):
        parser = session_end.build_parser()
        args = parser.parse_args([
            "--manifest", "/tmp/m.yaml",
            "--only", "session_log,extractions",
        ])
        assert args.only == ["session_log", "extractions"]

    def test_invalid_only_section_exits_nonzero(self, tmp_path):
        manifest_path = tmp_path / "m.yaml"
        manifest_path.write_text("date: 2026-05-09\ntopic: x\n")
        with pytest.raises(SystemExit) as exc:
            session_end.main([
                "--manifest", str(manifest_path),
                "--only", "session_log,nonsense",
            ])
        assert exc.value.code != 0

    def test_dry_run_flag_present(self):
        parser = session_end.build_parser()
        args = parser.parse_args(["--manifest", "/tmp/m.yaml", "--dry-run"])
        assert args.dry_run is True


class TestPersonalProjects:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    # --- Model validation ---

    def test_personal_slug_with_spaces_validates(self):
        pt = session_end.ProjectTouched(slug="InBloom Early Learning", note="kick-off", category="personal")
        assert pt.slug == "InBloom Early Learning"
        assert pt.category == "personal"

    def test_work_slug_with_spaces_rejects(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            session_end.ProjectTouched(slug="has spaces", note="x")  # default category="work"

    def test_work_slug_default_category_kebab_passes(self):
        pt = session_end.ProjectTouched(slug="foo-bar", note="x")
        assert pt.category == "work"

    # --- Wikilink rendering ---

    def test_projects_touched_personal_renders_pipe_alias_wikilink(self):
        manifest = session_end.SessionEndManifest(
            date="2026-05-09",
            topic="test-session",
            tags=["session"],
            last_updated_slug="2026-05-09-test-session",
            summary="Summary.",
            projects_touched=[
                session_end.ProjectTouched(
                    slug="InBloom Early Learning",
                    note="kick-off meeting",
                    category="personal",
                ),
            ],
            streams=[session_end.Stream(title="S", body="B")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
        )
        text = session_end.render_session_log(manifest, org_name="Chalktalk")
        assert "[[Personal/Projects/InBloom Early Learning/overview|InBloom Early Learning]] — kick-off meeting" in text

    def test_session_log_mixes_work_and_personal_projects_touched(self):
        manifest = session_end.SessionEndManifest(
            date="2026-05-09",
            topic="test-session",
            tags=["session"],
            last_updated_slug="2026-05-09-test-session",
            summary="Summary.",
            projects_touched=[
                session_end.ProjectTouched(slug="foo-bar", note="work note"),
                session_end.ProjectTouched(
                    slug="InBloom Early Learning",
                    note="personal note",
                    category="personal",
                ),
            ],
            streams=[session_end.Stream(title="S", body="B")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
        )
        text = session_end.render_session_log(manifest, org_name="Chalktalk")
        assert "[[Work/Chalktalk/Projects/foo-bar]] — work note" in text
        assert "[[Personal/Projects/InBloom Early Learning/overview|InBloom Early Learning]] — personal note" in text

    # --- append_to_project_doc ---

    def test_append_to_personal_project_doc(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="Test Project",
            section_title="First session",
            section_date="2026-05-09",
            body="Got started.",
            category="personal",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = (vault / "Personal/Projects/Test Project/overview.md").read_text()
        assert "## 2026-05-09 — First session" in text
        assert "Got started." in text
        assert "Existing personal project for tests." in text

    def test_personal_project_doc_missing_raises(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="Does Not Exist",
            section_title="x",
            section_date="2026-05-09",
            body="x",
            category="personal",
        )
        with pytest.raises(FileNotFoundError):
            session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")

    # --- write_new_project_doc ---

    def test_write_new_personal_project_doc_creates_subfolder(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        doc = session_end.NewProjectDoc(
            slug="My Garden",
            frontmatter={"type": "project", "status": "active", "tags": ["project", "personal"]},
            body="# My Garden\n\n## Overview\nTracking the garden.",
            category="personal",
        )
        session_end.write_new_project_doc(vault=vault, doc=doc, org_name="Chalktalk")
        path = vault / "Personal/Projects/My Garden/overview.md"
        assert path.exists()
        text = path.read_text()
        assert text.startswith("---\n")
        assert "type: project" in text
        assert "# My Garden" in text

    def test_personal_new_project_doc_collision_raises(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        doc = session_end.NewProjectDoc(
            slug="Test Project",  # fixture overview.md already exists
            frontmatter={"type": "project", "status": "active"},
            body="# Test Project",
            category="personal",
        )
        with pytest.raises(FileExistsError):
            session_end.write_new_project_doc(vault=vault, doc=doc, org_name="Chalktalk")

    # --- preflight ---

    def test_preflight_personal_project_update_missing(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest = session_end.SessionEndManifest(
            date="2026-05-09", topic="ok", tags=["session"],
            last_updated_slug="x", summary="x", projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x", learnings="x",
            files_modified=session_end.FilesModified(), next_steps="x",
            project_doc_updates=[
                session_end.ProjectDocUpdate(
                    slug="Nonexistent Personal",
                    section_title="x",
                    section_date="2026-05-09",
                    body="x",
                    category="personal",
                ),
            ],
        )
        problems = session_end.preflight_validate(
            manifest=manifest, vault=vault, org_name="Chalktalk",
            sections={"project_doc_updates"},
        )
        assert any("Nonexistent Personal" in p for p in problems)
        assert any("personal" in p.lower() for p in problems)

    def test_preflight_personal_new_project_doc_collision(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        manifest = session_end.SessionEndManifest(
            date="2026-05-09", topic="ok", tags=["session"],
            last_updated_slug="x", summary="x", projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x", learnings="x",
            files_modified=session_end.FilesModified(), next_steps="x",
            new_project_docs=[
                session_end.NewProjectDoc(
                    slug="Test Project",  # fixture already has this overview.md
                    frontmatter={"type": "project", "status": "active"},
                    body="x",
                    category="personal",
                ),
            ],
        )
        problems = session_end.preflight_validate(
            manifest=manifest, vault=vault, org_name="Chalktalk",
            sections={"new_project_docs"},
        )
        assert any("Test Project" in p for p in problems)
        assert any("personal" in p.lower() for p in problems)


class TestStructuredProjectDocUpdates:
    """Tests for the four structured update modes on project docs."""

    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def _proj_path(self, vault):
        return vault / "Work/Chalktalk/Projects/existing-project.md"

    def _personal_proj_path(self, vault):
        return vault / "Personal/Projects/Test Project/overview.md"

    # -- Status --

    def test_status_replace_replaces_status_body_only(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            status="🔴 **Blocked.** Waiting on infra team.",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = self._proj_path(vault).read_text()
        # New status body present
        assert "🔴 **Blocked.** Waiting on infra team." in text
        # Old status body gone
        assert "Running smoothly" not in text
        # Other sections untouched
        assert "## Overview" in text
        assert "Pre-existing description." in text
        assert "## Next Steps" in text
        assert "Ship v1 by end of month." in text

    def test_status_creates_section_when_missing(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        # Write a project doc without ## Status
        proj = self._proj_path(vault)
        proj.write_text(
            "---\ntype: project\n---\n\n# No Status\n\n## Overview\nContent here.\n"
        )
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            status="🟢 **Active.** Newly added.",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = proj.read_text()
        assert "## Status\n" in text
        assert "🟢 **Active.** Newly added." in text
        assert "## Overview" in text

    # -- Recent activity --

    def test_recent_activity_prepends_at_top_of_section(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="New hardening pass",
                body="- Fixed 5 bugs.\n- Deployed.",
            ),
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = self._proj_path(vault).read_text()
        new_idx = text.index("New hardening pass")
        old_idx = text.index("Second session")
        assert new_idx < old_idx, "New entry should appear before existing entries"

    def test_recent_activity_trims_to_three_when_overflow(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        # First add a 3rd entry to make 3 total in the section
        proj = self._proj_path(vault)
        text = proj.read_text()
        # Insert a 3rd entry right after the ## Recent activity heading
        text = text.replace(
            "## Recent activity\n\n### 2026-04-20",
            "## Recent activity\n\n### 2026-04-30 — Third entry\n- Added before overflow test.\n\n### 2026-04-20",
        )
        proj.write_text(text)

        # Now add a 4th entry via structured update
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="Fourth entry causes trim",
                body="- This should be entry 1 of 3.",
            ),
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        result = self._proj_path(vault).read_text()

        # Count ### entries in the Recent activity section
        lines = result.splitlines()
        in_section = False
        h3_count = 0
        for line in lines:
            if line.strip() == "## Recent activity":
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section and line.startswith("### "):
                h3_count += 1

        assert h3_count == 3, f"Expected 3 entries after trim, got {h3_count}"
        # The oldest entry (First session) should be dropped
        assert "First session" not in result
        # The new entry should be present
        assert "Fourth entry causes trim" in result

    def test_recent_activity_under_three_no_trim(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        # Fixture has 2 entries; adding 1 more => 3 total, no trim
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="Third entry no trim",
                body="- Should coexist with both existing entries.",
            ),
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        result = self._proj_path(vault).read_text()

        lines = result.splitlines()
        in_section = False
        h3_count = 0
        for line in lines:
            if line.strip() == "## Recent activity":
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section and line.startswith("### "):
                h3_count += 1

        assert h3_count == 3
        assert "Third entry no trim" in result
        assert "Second session" in result
        assert "First session" in result

    def test_recent_activity_creates_section_when_missing(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        proj = self._proj_path(vault)
        proj.write_text("---\ntype: project\n---\n\n# No Activity\n\n## Overview\nContent.\n")
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="First entry ever",
                body="- Bootstrap.",
            ),
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = proj.read_text()
        assert "## Recent activity" in text
        assert "### 2026-05-09 — First entry ever" in text
        assert "Bootstrap." in text

    # -- Next Steps --

    def test_next_steps_replace_replaces_body(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            next_steps="- Deploy to prod.\n- Write release notes.",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = self._proj_path(vault).read_text()
        # New body present
        assert "Deploy to prod." in text
        assert "Write release notes." in text
        # Old body gone
        assert "Ship v1 by end of month." not in text
        assert "Write docs." not in text

    def test_next_steps_creates_section_when_missing(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        proj = self._proj_path(vault)
        proj.write_text("---\ntype: project\n---\n\n# No Steps\n\n## Overview\nContent.\n")
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            next_steps="- Do the thing.",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = proj.read_text()
        assert "## Next Steps" in text
        assert "Do the thing." in text

    # -- Related Sessions --

    def test_related_session_appends_bullet(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            related_session="[[Sessions/2026-05/2026-05-09-test]] — new work",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = self._proj_path(vault).read_text()
        assert "- [[Sessions/2026-05/2026-05-09-test]] — new work" in text
        # Old bullet still there
        assert "2026-04-10-initial-setup" in text
        # New bullet should appear after old one (appended at end of section)
        assert text.index("2026-05-09-test") > text.index("2026-04-10-initial-setup")

    def test_related_session_creates_section_when_missing(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        proj = self._proj_path(vault)
        proj.write_text("---\ntype: project\n---\n\n# No Sessions\n\n## Overview\nContent.\n")
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            related_session="[[Sessions/2026-05/2026-05-09-test]] — first session",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = proj.read_text()
        assert "## Related Sessions" in text
        assert "- [[Sessions/2026-05/2026-05-09-test]] — first session" in text

    # -- Legacy --

    def test_legacy_free_form_append_still_works(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            section_title="Legacy section",
            section_date="2026-05-09",
            body="Legacy body text.",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = self._proj_path(vault).read_text()
        assert "## 2026-05-09 — Legacy section" in text
        assert "Legacy body text." in text
        # Frontmatter and existing sections untouched
        assert "type: project" in text
        assert "Pre-existing description." in text

    # -- Combined --

    def test_combined_update_all_four_structured_modes(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            status="🔵 **Review.** Under code review.",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="Combined update test",
                body="- Ran all four modes.",
            ),
            next_steps="- Merge PR.\n- Tag release.",
            related_session="[[Sessions/2026-05/2026-05-09-combined]] — combined test",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = self._proj_path(vault).read_text()
        assert "🔵 **Review.** Under code review." in text
        assert "Combined update test" in text
        assert "Merge PR." in text
        assert "[[Sessions/2026-05/2026-05-09-combined]] — combined test" in text
        # Old status gone
        assert "Running smoothly" not in text
        # Old next steps gone
        assert "Ship v1 by end of month." not in text

    # -- Personal project --

    def test_personal_project_supports_structured_updates(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="Test Project",
            category="personal",
            status="🟢 **Active.** Good progress.",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="Personal session",
                body="- Made progress.",
            ),
            next_steps="- Finish prototype.",
            related_session="[[Sessions/2026-05/2026-05-09-personal]] — personal work",
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        text = self._personal_proj_path(vault).read_text()
        assert "🟢 **Active.** Good progress." in text
        assert "Personal session" in text
        assert "Finish prototype." in text
        assert "[[Sessions/2026-05/2026-05-09-personal]] — personal work" in text

    # -- Validation --

    def test_validator_rejects_empty_update(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc:
            session_end.ProjectDocUpdate(slug="existing-project")
        assert "at least one update field" in str(exc.value)

    def test_validator_rejects_partial_legacy(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc:
            session_end.ProjectDocUpdate(
                slug="existing-project",
                section_title="Only title, no date or body",
            )
        assert "section_title, section_date, AND body" in str(exc.value)

    # -- Recent Work alias --

    def test_recent_work_alias(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        proj = self._proj_path(vault)
        # Replace "Recent activity" with "Recent Work" alias in the fixture
        text = proj.read_text().replace("## Recent activity", "## Recent Work")
        proj.write_text(text)

        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="Found via alias",
                body="- Used Recent Work heading.",
            ),
        )
        session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        result = proj.read_text()
        assert "Found via alias" in result
        # New entry should be at the top
        assert result.index("Found via alias") < result.index("Second session")


class TestPrioritiesUpdate:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def _focus_path(self, vault):
        return vault / "Context/current-focus.md"

    def test_priorities_replace_replaces_body(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        updates = session_end.FocusUpdates(
            priorities="1. New thing\n2. Other",
        )
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = self._focus_path(vault).read_text()
        # New content present
        assert "1. New thing" in text
        assert "2. Other" in text
        # Old content gone
        assert "Ship the helper" not in text
        # Other sections untouched
        assert "## Active Projects" in text
        assert "## Complete" in text
        assert "Foo is active" in text

    def test_priorities_none_leaves_section_alone(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        updates = session_end.FocusUpdates(
            upsert=[
                session_end.FocusUpsert(
                    slug="foo",
                    status_line="**🔴 Foo changed.** Updated.",
                ),
            ],
            # priorities=None by default
        )
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = self._focus_path(vault).read_text()
        # Priorities body unchanged
        assert "1. Ship the helper" in text
        assert "2. Wait for CodeRabbit" in text
        assert "3. Phase 2 ritual rewrite" in text

    def test_priorities_creates_section_when_missing(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        focus_path = self._focus_path(vault)
        # Write a current-focus.md without ## Priorities
        focus_path.write_text(
            "---\ntype: index\nlast-updated: 2026-04-30-old-session\ntags: [focus]\n---\n\n"
            "# Current Focus\n\n## Active Projects\n\n## Complete\n"
        )
        updates = session_end.FocusUpdates(priorities="1. Foo")
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = focus_path.read_text()
        assert "## Priorities" in text
        assert "1. Foo" in text
        # Section appended after the rest of the body
        assert text.index("## Priorities") > text.index("## Complete")

    def test_priorities_preserves_frontmatter_and_last_updated_bump(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        updates = session_end.FocusUpdates(priorities="1. Updated priority")
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-prio-bump", org_name="Chalktalk",
        )
        text = self._focus_path(vault).read_text()
        # Frontmatter still starts the file with the right type/tags fields
        assert text.startswith("---\n")
        assert "type: index" in text
        assert "tags: [focus]" in text
        # last-updated bumped
        assert "last-updated: 2026-05-09-prio-bump" in text
        assert "last-updated: 2026-04-30-old-session" not in text
        # Priorities replaced
        assert "1. Updated priority" in text
        assert "Ship the helper" not in text


class TestSourceFiles:
    """Tests for Source file writing (render_source_file, source_file_path, write_source_files)."""

    def _make_source(self, **overrides):
        defaults = dict(
            url="https://example.com/article",
            title="Example Article",
            slug="example-article",
            type="article",
            tags=["python", "testing"],
            summary="A two-sentence objective summary. It covers key points.",
            takeaways=["Takeaway one.", "Takeaway two."],
            why="Came up while discussing source file writing.",
        )
        defaults.update(overrides)
        return session_end.Source(**defaults)

    def _session_date(self):
        return Date(2026, 5, 9)

    def _session_log_filename(self):
        return "2026-05-09-my-session"

    # --- render_source_file ---

    def test_writes_source_file_with_full_template(self):
        source = self._make_source()
        text = session_end.render_source_file(
            source, self._session_date(), self._session_log_filename()
        )
        # Frontmatter
        assert "---\n" in text
        assert "date: 2026-05-09\n" in text
        assert f"url: {source.url}\n" in text
        assert f"type: {source.type}\n" in text
        assert "tags: [python, testing]\n" in text
        # Title heading
        assert f"# {source.title}\n" in text
        # Summary section
        assert "## Summary\n" in text
        assert source.summary in text
        # Takeaways section
        assert "## Takeaways\n" in text
        assert "- Takeaway one.\n" in text
        assert "- Takeaway two.\n" in text
        # Context section
        assert "## Context\n" in text
        assert "[[Sessions/2026-05/2026-05-09-my-session]]" in text
        assert source.why in text

    def test_source_file_filename_uses_session_date_and_slug(self):
        source = self._make_source(slug="my-source")
        path = session_end.source_file_path(source, self._session_date())
        assert path == "Sources/2026-05-09-my-source.md"

    def test_existing_source_file_skipped_with_warning(self, tmp_path, capsys):
        source = self._make_source(slug="my-source")
        # Pre-create the file
        sources_dir = tmp_path / "Sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        existing_file = sources_dir / "2026-05-09-my-source.md"
        existing_file.write_text("---\nexisting: true\n---\n")

        session_end.write_source_files(
            vault=tmp_path,
            sources=[source],
            session_date=self._session_date(),
            session_log_filename=self._session_log_filename(),
        )

        # File must be unchanged
        assert existing_file.read_text() == "---\nexisting: true\n---\n"
        # Warning on stderr
        captured = capsys.readouterr()
        assert "skipped" in captured.err.lower() or "exists" in captured.err.lower()

    def test_session_log_renders_wikilink_not_markdown_link(self):
        manifest = session_end.SessionEndManifest(
            date="2026-05-09",
            topic="my-session",
            tags=["session"],
            last_updated_slug="2026-05-09-my-session",
            summary="Summary.",
            projects_touched=[],
            streams=[session_end.Stream(title="S", body="B")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
            sources_captured=[
                self._make_source(slug="my-source"),
            ],
        )
        text = session_end.render_session_log(manifest, org_name="Chalktalk")
        # Must contain wikilink form
        assert "[[Sources/2026-05-09-my-source|Example Article]]" in text
        # Must NOT contain raw markdown link form
        assert "[Example Article](https://example.com/article)" not in text

    def test_sources_skipped_when_session_log_section_excluded(self, tmp_path):
        source = self._make_source(slug="skipped-source")
        manifest = session_end.SessionEndManifest(
            date="2026-05-09",
            topic="my-session",
            tags=["session"],
            last_updated_slug="2026-05-09-my-session",
            summary="Summary.",
            projects_touched=[],
            streams=[session_end.Stream(title="S", body="B")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
            sources_captured=[source],
        )
        # Copy vault fixture
        import shutil
        vault = tmp_path / "vault"
        shutil.copytree(
            Path(__file__).parent / "fixtures" / "vault", vault
        )
        rc = session_end.run(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            dry_run=False,
            sections={"extractions"},  # session_log excluded
        )
        assert rc == 0
        assert not (vault / "Sources" / "2026-05-09-skipped-source.md").exists()

    def test_sources_written_with_session_log_section(self, tmp_path):
        source = self._make_source(slug="written-source")
        manifest = session_end.SessionEndManifest(
            date="2026-05-09",
            topic="my-session",
            tags=["session"],
            last_updated_slug="2026-05-09-my-session",
            summary="Summary.",
            projects_touched=[],
            streams=[session_end.Stream(title="S", body="B")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
            sources_captured=[source],
        )
        import shutil
        vault = tmp_path / "vault"
        shutil.copytree(
            Path(__file__).parent / "fixtures" / "vault", vault
        )
        rc = session_end.run(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            dry_run=False,
            sections={"session_log"},
        )
        assert rc == 0
        source_file = vault / "Sources" / "2026-05-09-written-source.md"
        assert source_file.exists()
        # Session log also written
        assert (vault / "Sessions/2026-05/2026-05-09-my-session.md").exists()
        # Session log references source via wikilink
        log_text = (vault / "Sessions/2026-05/2026-05-09-my-session.md").read_text()
        assert "[[Sources/2026-05-09-written-source|Example Article]]" in log_text

    def test_dry_run_does_not_write_sources_but_previews_them(self, tmp_path, capsys):
        source = self._make_source(slug="dry-source")
        manifest = session_end.SessionEndManifest(
            date="2026-05-09",
            topic="my-session",
            tags=["session"],
            last_updated_slug="2026-05-09-my-session",
            summary="Summary.",
            projects_touched=[],
            streams=[session_end.Stream(title="S", body="B")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
            sources_captured=[source],
        )
        import shutil
        vault = tmp_path / "vault"
        shutil.copytree(
            Path(__file__).parent / "fixtures" / "vault", vault
        )
        rc = session_end.run(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            dry_run=True,
            sections={"session_log"},
        )
        assert rc == 0
        # No file created
        assert not (vault / "Sources" / "2026-05-09-dry-source.md").exists()
        # Preview line in stdout
        captured = capsys.readouterr()
        assert "would write source" in captured.out.lower()

    def test_takeaways_empty_renders_section_with_no_bullets(self):
        source = self._make_source(takeaways=[])
        text = session_end.render_source_file(
            source, self._session_date(), self._session_log_filename()
        )
        assert "## Takeaways\n" in text
        # No bullet lines between Takeaways and Context
        takeaways_idx = text.index("## Takeaways\n")
        context_idx = text.index("## Context\n")
        between = text[takeaways_idx + len("## Takeaways\n"):context_idx]
        # Only whitespace/newlines between the two headings (no bullet items)
        assert not any(line.startswith("- ") for line in between.splitlines())

    def test_multiple_sources_all_written(self, tmp_path):
        sources = [
            self._make_source(slug="src-one", title="Source One"),
            self._make_source(slug="src-two", title="Source Two"),
            self._make_source(slug="src-three", title="Source Three"),
        ]
        session_end.write_source_files(
            vault=tmp_path,
            sources=sources,
            session_date=self._session_date(),
            session_log_filename=self._session_log_filename(),
        )
        for slug in ["src-one", "src-two", "src-three"]:
            assert (tmp_path / "Sources" / f"2026-05-09-{slug}.md").exists()


class TestAppendIdempotency:
    """Enrichment #2: Shipping Log and Brag Doc appends are idempotent on retry."""

    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_shipping_append_idempotent_when_bullet_already_present(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        entry = session_end.ShippingEntry(
            date="2026-05-09",
            label="Already shipped",
            context="existing ctx",
        )
        # Build the bullet that the function would insert
        bullet = session_end.format_shipping_bullet(entry, "2026-05-09-test")

        # Pre-write the bullet into the shipping log
        log_path = vault / "Work/Chalktalk/Shipping Log.md"
        original = log_path.read_text()
        log_path.write_text(original + bullet + "\n")
        before = log_path.read_text()

        # Call append_to_shipping_log -- should detect duplicate and skip
        session_end.append_to_shipping_log(
            vault=vault,
            entry=entry,
            session_log_filename="2026-05-09-test",
            org_name="Chalktalk",
        )

        after = log_path.read_text()
        assert after == before, "File should be unchanged on idempotent retry"
        captured = capsys.readouterr()
        assert "skipped" in captured.err

    def test_brag_append_idempotent_when_bullet_already_present(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        entry = session_end.BragEntry(
            quarter="2026 Q2",
            date="2026-05-09",
            body="already bragged about this.",
        )
        # Build the bullet that the function would insert
        bullet = session_end.format_brag_bullet(entry, "2026-05-09-test")

        # Pre-write the bullet into the brag doc
        brag_path = vault / "Personal/Brag Doc.md"
        original = brag_path.read_text()
        brag_path.write_text(original + bullet + "\n")
        before = brag_path.read_text()

        # Call append_to_brag_doc -- should detect duplicate and skip
        session_end.append_to_brag_doc(
            vault=vault,
            entry=entry,
            session_log_filename="2026-05-09-test",
        )

        after = brag_path.read_text()
        assert after == before, "File should be unchanged on idempotent retry"
        captured = capsys.readouterr()
        assert "skipped" in captured.err

    def test_shipping_append_normal_when_bullet_differs(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.ShippingEntry(
            date="2026-05-09",
            label="A fresh new entry",
        )
        log_path = vault / "Work/Chalktalk/Shipping Log.md"
        before = log_path.read_text()

        session_end.append_to_shipping_log(
            vault=vault,
            entry=entry,
            session_log_filename="2026-05-09-test",
            org_name="Chalktalk",
        )

        after = log_path.read_text()
        assert after != before, "A new bullet should have been appended"
        assert "A fresh new entry" in after

    def test_idempotency_doesnt_match_partial_substring(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        # Write a partial substring of what the bullet would look like into the log
        log_path = vault / "Work/Chalktalk/Shipping Log.md"
        original = log_path.read_text()
        # Only a fragment of the bullet, NOT the full line
        log_path.write_text(original + "partial fragment of the label\n")

        entry = session_end.ShippingEntry(
            date="2026-05-09",
            label="partial fragment of the label but this is a full new bullet",
        )
        before = log_path.read_text()

        session_end.append_to_shipping_log(
            vault=vault,
            entry=entry,
            session_log_filename="2026-05-09-test",
            org_name="Chalktalk",
        )

        after = log_path.read_text()
        # The full bullet line differs from the fragment -- append should have happened
        assert after != before, "A distinct bullet should have been appended"
        captured = capsys.readouterr()
        assert "skipped" not in captured.err


class TestTagDedup:
    """Enrichment #3: Frontmatter tags are deduplicated with stable (first-seen) order."""

    def _minimal_manifest(self, tags):
        return session_end.SessionEndManifest(
            date="2026-05-09",
            topic="test-session",
            tags=tags,
            last_updated_slug="2026-05-09-test-session",
            summary="Summary.",
            projects_touched=[],
            streams=[session_end.Stream(title="S", body="B")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
        )

    def _decision(self, tags):
        return session_end.Decision(
            slug="2026-05-09-test-decision",
            title="Test",
            owner="Mo",
            tags=tags,
            context="ctx",
            options_considered="opt",
            chosen="A",
            reasoning="r",
            consequences="c",
        )

    def test_session_log_tags_deduped(self):
        manifest = self._minimal_manifest(tags=["a", "b", "a", "c", "b"])
        text = session_end.render_session_log(manifest, org_name="Chalktalk")
        assert "tags: [a, b, c]\n" in text

    def test_decision_tags_deduped(self):
        decision = self._decision(tags=["decision", "work", "decision", "test", "work"])
        text = session_end.render_decision_file(
            decision,
            source_session_wikilink="[[Sessions/2026-05/2026-05-09-test]]",
            session_date=Date(2026, 5, 9),
        )
        assert "tags: [decision, work, test]\n" in text

    def test_dedup_preserves_first_seen_order(self):
        result = session_end._dedup_preserve_order(["c", "a", "c", "b", "a"])
        assert result == ["c", "a", "b"]


class TestProjectsTouchedConsistency:
    """Enrichment #4: preflight warns when projects_touched and project_doc_updates disagree."""

    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def _base_manifest(self, **overrides):
        defaults = dict(
            date="2026-05-09",
            topic="ok",
            tags=["session"],
            last_updated_slug="2026-05-09-ok",
            summary="x",
            projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x",
            learnings="x",
            files_modified=session_end.FilesModified(),
            next_steps="x",
            project_doc_updates=[],
            new_project_docs=[],
        )
        defaults.update(overrides)
        return session_end.SessionEndManifest(**defaults)

    def test_warns_when_update_missing_from_projects_touched(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        manifest = self._base_manifest(
            project_doc_updates=[
                session_end.ProjectDocUpdate(
                    slug="existing-project",
                    status="active",
                ),
            ],
            # projects_touched is empty -- existing-project not mentioned there
        )
        problems = session_end.preflight_validate(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            sections={"session_log", "project_doc_updates"},
        )
        assert problems == [], "Consistency mismatch should not block the run"
        captured = capsys.readouterr()
        assert "existing-project" in captured.err
        assert "not in projects_touched" in captured.err

    def test_warns_when_projects_touched_missing_from_updates(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        manifest = self._base_manifest(
            projects_touched=[
                session_end.ProjectTouched(slug="existing-project", note="did work"),
            ],
            # No project_doc_updates or new_project_docs for existing-project
        )
        problems = session_end.preflight_validate(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            sections={"session_log", "project_doc_updates"},
        )
        assert problems == [], "Consistency mismatch should not block the run"
        captured = capsys.readouterr()
        assert "existing-project" in captured.err
        assert "no matching project_doc_updates" in captured.err

    def test_no_warning_when_consistent(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        manifest = self._base_manifest(
            projects_touched=[
                session_end.ProjectTouched(slug="existing-project", note="did work"),
            ],
            project_doc_updates=[
                session_end.ProjectDocUpdate(
                    slug="existing-project",
                    status="active",
                ),
            ],
        )
        problems = session_end.preflight_validate(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            sections={"session_log", "project_doc_updates"},
        )
        assert problems == []
        captured = capsys.readouterr()
        # No consistency warnings
        assert "not in projects_touched" not in captured.err
        assert "no matching project_doc_updates" not in captured.err

    def test_categories_distinguished(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        # projects_touched has (existing-project, work), new_project_docs has (existing-project, personal).
        # The (slug, category) tuples differ so both directions should warn.
        # Use new_project_docs to avoid the project_doc_updates file-existence preflight check.
        manifest = self._base_manifest(
            projects_touched=[
                session_end.ProjectTouched(
                    slug="existing-project",
                    note="work project",
                    category="work",
                ),
            ],
            new_project_docs=[
                session_end.NewProjectDoc(
                    slug="existing-project",
                    category="personal",  # different category -- (slug, category) tuples differ
                    frontmatter={"type": "project", "status": "active"},
                    body="New personal project.",
                ),
            ],
        )
        problems = session_end.preflight_validate(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            sections={"session_log", "new_project_docs"},
        )
        assert problems == [], "Category mismatch should be a warning, not a blocker"
        captured = capsys.readouterr()
        # Both directions warn: update not in touched, touched not in updates
        assert "not in projects_touched" in captured.err
        assert "no matching project_doc_updates" in captured.err

    def test_no_warning_when_session_log_section_excluded(self, tmp_path, capsys):
        vault = self._setup_vault(tmp_path)
        manifest = self._base_manifest(
            projects_touched=[
                session_end.ProjectTouched(slug="existing-project", note="did work"),
            ],
            project_doc_updates=[
                session_end.ProjectDocUpdate(
                    slug="existing-project",
                    category="personal",  # intentionally inconsistent
                    status="active",
                ),
            ],
        )
        problems = session_end.preflight_validate(
            manifest=manifest,
            vault=vault,
            org_name="Chalktalk",
            sections={"extractions"},  # session_log not included -- check should not run
        )
        assert problems == []
        captured = capsys.readouterr()
        assert "not in projects_touched" not in captured.err
        assert "no matching project_doc_updates" not in captured.err
