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

    def test_category_defaults_to_work(self):
        # Premise: the fixture does not set `category`, so this test measures the DEFAULT
        # rather than an explicit value. If the fixture ever starts passing one, this
        # assertion stops testing what it claims to.
        assert "category" not in self._decision().model_fields_set
        assert self._decision().category == "work"

    def test_personal_decision_lands_outside_the_work_org(self):
        """A personal decision must not be filed in the work org's decision log.

        The assertion is a RELATIONSHIP, not a retyped path: whatever the work org is
        called, a personal decision's path must not sit under it, and the two categories
        must disagree on destination while agreeing on filename.
        """
        session_date = Date(2026, 5, 9)
        work = self._decision(slug="test-decision", category="work")
        personal = self._decision(slug="test-decision", category="personal")

        work_path = session_end.decision_file_path(work, session_date, org_name="Chalktalk")
        personal_path = session_end.decision_file_path(personal, session_date, org_name="Chalktalk")

        assert personal_path != work_path
        assert not personal_path.startswith("Work/")
        assert personal_path.startswith("Personal/")
        # Same slug and date => same filename; only the parent differs.
        assert personal_path.rsplit("/", 1)[1] == work_path.rsplit("/", 1)[1]

    def test_personal_destination_is_org_name_independent(self):
        """Renaming the work org must not move personal decisions."""
        decision = self._decision(slug="test-decision", category="personal")
        session_date = Date(2026, 5, 9)
        assert session_end.decision_file_path(
            decision, session_date, org_name="Chalktalk"
        ) == session_end.decision_file_path(decision, session_date, org_name="SomeOtherOrg")

    def test_decision_slug_stays_kebab_case_in_both_categories(self):
        """Personal PROJECT slugs allow spaces/Title Case; decision slugs never do.

        NOT a test of the category feature — it stays green with the feature fully
        reverted, because slug validation is category-independent by design and that
        IS the claim. It guards against someone later loosening `Decision.slug` to
        match personal project slugs. Kept out of the mutation-proved set deliberately.
        """
        from pydantic import ValidationError

        for category in ("work", "personal"):
            with pytest.raises(ValidationError):
                self._decision(slug="Some Decision With Spaces", category=category)

    def test_dated_slug_honours_personal_category(self):
        """Closes the dated-slug x personal gap: the date branch is computed BEFORE
        the category branch, so both must compose."""
        decision = self._decision(slug="2026-05-09-test-decision", category="personal")
        path = session_end.decision_file_path(decision, session_date=Date(2026, 5, 9))
        assert path == "Personal/Decisions/2026-05-09-test-decision.md"

    def test_category_reaches_the_note_frontmatter(self):
        """The work/personal split must be carried by the note, not only by its folder.

        Asserted as a relationship over both categories rather than one retyped literal.
        """
        for category in ("work", "personal"):
            text = session_end.render_decision_file(
                self._decision(category=category),
                source_session_wikilink="[[Sessions/2026-05/2026-05-09-test-session]]",
                session_date=Date(2026, 5, 9),
            )
            frontmatter = text.split("---")[1]
            assert f"category: {category}" in frontmatter

    def test_personal_decision_file_written_under_personal(self, tmp_path):
        """End-to-end: the file actually lands on disk where the path function says."""
        vault = tmp_path / "vault"
        vault.mkdir()
        decision = self._decision(slug="test-decision", category="personal")
        reports = session_end.write_decision_files(
            vault=vault,
            decisions=[decision],
            session_date=Date(2026, 5, 9),
            session_log_filename="2026-05-09-test-session",
        )
        expected = session_end.decision_file_path(decision, Date(2026, 5, 9))
        assert (vault / expected).exists()
        assert [r.path for r in reports] == [expected]
        # The parent directory is created on demand — Personal/Decisions/ need not pre-exist.
        assert not (vault / "Work").exists()


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

    def test_creates_staging_section_at_end_of_file(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.BragEntry(
            date="2026-05-09",
            body="codified the cross-model review pattern.",
        )
        # Trailing content AFTER the quarter section, so "below Q1" and "at end of
        # file" are distinguishable — otherwise the EOF claim has no test.
        brag_path = vault / "Personal/Brag Doc.md"
        brag_path.write_text(
            brag_path.read_text()
            + "\n## 2025 Q4\n- **2025-11-02** — older quarter entry. [[Sessions/2025-11/x]]\n"
        )
        session_end.append_to_brag_doc(
            vault=vault, entry=entry, session_log_filename="2026-05-09-may",
        )
        log = brag_path.read_text()
        assert "## Staging" in log
        # Staging lives BELOW every accepted quarter section, at the very end.
        assert log.index("## Staging") > log.index("## 2026 Q1")
        assert log.index("## Staging") > log.index("## 2025 Q4")
        bullet = session_end.format_brag_bullet(entry, "2026-05-09-may")
        assert log.rstrip().splitlines()[-2:] == ["## Staging", bullet]
        assert "codified the cross-model review pattern." in log

    def test_prepends_under_existing_staging_and_leaves_quarters_alone(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        first = session_end.BragEntry(date="2026-05-08", body="older staged item.")
        second = session_end.BragEntry(date="2026-05-09", body="newer staged item.")
        session_end.append_to_brag_doc(
            vault=vault, entry=first, session_log_filename="2026-05-08-a",
        )
        session_end.append_to_brag_doc(
            vault=vault, entry=second, session_log_filename="2026-05-09-b",
        )
        log = (vault / "Personal/Brag Doc.md").read_text()
        assert log.count("## Staging") == 1
        assert log.index("newer staged item.") < log.index("older staged item.")
        # Quarter content untouched, still above staging.
        assert log.index("old brag entry") < log.index("## Staging")

    def test_bullet_format(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        entry = session_end.BragEntry(
            date="2026-05-09", body="did the thing.",
        )
        session_end.append_to_brag_doc(
            vault=vault, entry=entry, session_log_filename="2026-05-09-test",
        )
        log = (vault / "Personal/Brag Doc.md").read_text()
        assert "- **2026-05-09** — did the thing. [[Sessions/2026-05/2026-05-09-test]]" in log

    def test_quarter_field_rejected(self):
        """Schema change is loud: a stale manifest still carrying `quarter` must fail
        validation, not be silently ignored (pydantic default is extra='ignore')."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc:
            session_end.BragEntry(
                quarter="2026 Q2",
                date="2026-05-09",
                body="did the thing.",
            )
        # Pin the MECHANISM, not the message: a future re-added `quarter` field with a
        # tightened pattern would also raise with "quarter" in the text and pass a
        # substring check, hiding exactly the regression this test exists to catch.
        assert [e["type"] for e in exc.value.errors()] == ["extra_forbidden"]
        assert exc.value.errors()[0]["loc"] == ("quarter",)

    def test_prepend_branch_change_report_names_op_and_bullet(self, tmp_path):
        """The prepend branch's summary needs its own coverage: the shared fixture has no
        ## Staging, so every other report test exercises only the heading-creation branch."""
        vault = self._setup_vault(tmp_path)
        first = session_end.BragEntry(date="2026-05-08", body="first staged item.")
        second = session_end.BragEntry(date="2026-05-09", body="second staged item.")
        session_end.append_to_brag_doc(
            vault=vault, entry=first, session_log_filename="2026-05-08-a",
        )
        rpt = session_end.append_to_brag_doc(
            vault=vault, entry=second, session_log_filename="2026-05-09-b",
        )
        expected_bullet = session_end.format_brag_bullet(second, "2026-05-09-b")
        assert rpt.summary == ["## Staging: prepended 1 entry", f"+ {expected_bullet}"]

    def test_skips_entry_already_culled_to_the_archive(self, tmp_path):
        """The promotion pass MOVES culled lines to Brag Archive.md, so an in-file-only
        dedupe check fails open: a documented `--only extractions` retry would resurrect
        an entry the promotion judge deliberately rejected."""
        vault = self._setup_vault(tmp_path)
        entry = session_end.BragEntry(date="2026-05-09", body="culled by the pass.")
        bullet = session_end.format_brag_bullet(entry, "2026-05-09-test")

        archive = vault / "Personal/Brag Archive.md"
        archive.write_text(f"# Brag Archive\n\n## 2026-05\n{bullet}\n")
        brag_path = vault / "Personal/Brag Doc.md"
        before = brag_path.read_text()

        rpt = session_end.append_to_brag_doc(
            vault=vault, entry=entry, session_log_filename="2026-05-09-test",
        )
        assert brag_path.read_text() == before, "archived entry must not be re-staged"
        assert any("archive" in s for s in rpt.summary), f"got: {rpt.summary}"


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

    def test_upsert_personal_new_writes_personal_wikilink(self, tmp_path):
        """category: personal must emit the Personal/.../overview pipe-alias
        heading, not the Work/<Org>/Projects form (which would be a broken link)."""
        vault = self._setup_vault(tmp_path)
        updates = session_end.FocusUpdates(
            upsert=[
                session_end.FocusUpsert(
                    slug="My Side Project",
                    category="personal",
                    status_line="**🟢 Kickoff.** First milestone planned.",
                ),
            ],
        )
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        text = (vault / "Context/current-focus.md").read_text()
        assert "### [[Personal/Projects/My Side Project/overview|My Side Project]]" in text
        assert "Work/Chalktalk/Projects/My Side Project" not in text

    def test_upsert_personal_replaces_existing_personal_block(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        focus_path = vault / "Context/current-focus.md"
        text = focus_path.read_text()
        text = text.replace(
            "## Active Projects\n",
            "## Active Projects\n\n"
            "### [[Personal/Projects/side-thing/overview|side-thing]]\n"
            "Old side-thing status.\n",
        )
        focus_path.write_text(text)
        updates = session_end.FocusUpdates(
            upsert=[
                session_end.FocusUpsert(
                    slug="side-thing",
                    category="personal",
                    status_line="New side-thing status.",
                ),
            ],
        )
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        result = focus_path.read_text()
        assert "Old side-thing status." not in result
        assert result.count("### [[Personal/Projects/side-thing/overview|side-thing]]") == 1
        assert "New side-thing status." in result

    def test_remove_finds_personal_entry(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        focus_path = vault / "Context/current-focus.md"
        text = focus_path.read_text()
        text = text.replace(
            "## Active Projects\n",
            "## Active Projects\n\n"
            "### [[Personal/Projects/side-thing/overview|side-thing]]\n"
            "Side-thing status to be removed.\n",
        )
        focus_path.write_text(text)
        updates = session_end.FocusUpdates(remove=["side-thing"])
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="2026-05-09-test", org_name="Chalktalk",
        )
        result = focus_path.read_text()
        assert "side-thing" not in result

    def test_focus_upsert_personal_slug_validation(self):
        from pydantic import ValidationError

        # Personal slugs allow spaces / Title Case; work slugs stay kebab-case.
        session_end.FocusUpsert(slug="My Side Project", category="personal", status_line="x")
        with pytest.raises(ValidationError):
            session_end.FocusUpsert(slug="My Side Project", status_line="x")

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


class TestStalenessAndRetire:
    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_move_to_retired_adds_marker_and_section(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        session_end.process_focus_updates(
            vault=vault, updates=session_end.FocusUpdates(move_to_retired=["foo"]),
            last_updated_slug="2026-06-19-test", org_name="Chalktalk",
            today=Date(2026, 6, 19),
        )
        text = (vault / "Context/current-focus.md").read_text()
        assert "Projects/foo]]" not in text.split("## Complete")[0]
        assert "[[Work/Chalktalk/Projects/foo]] 🗄️" in text.split("## Retired Projects")[1]

    def test_upsert_stamps_last_worked_on(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(
                upsert=[session_end.FocusUpsert(slug="foo", status_line="**🟢 still going.**")]
            ),
            last_updated_slug="2026-06-19-test", org_name="Chalktalk",
            today=Date(2026, 6, 19),
        )
        meta = session_end.load_focus_meta(vault)
        assert meta["projects"]["foo"]["last_worked_on"] == "2026-06-19"

    def test_snooze_sets_future_date_and_resnooze_extends(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        session_end.process_focus_updates(
            vault=vault, updates=session_end.FocusUpdates(snooze=["foo"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 6, 19),
        )
        assert session_end.load_focus_meta(vault)["projects"]["foo"]["snooze_until"] == "2026-07-03"
        # Re-snooze from a later day resets the window (no cap).
        session_end.process_focus_updates(
            vault=vault, updates=session_end.FocusUpdates(snooze=["foo"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 7, 3),
        )
        assert session_end.load_focus_meta(vault)["projects"]["foo"]["snooze_until"] == "2026-07-17"

    def test_stale_detected_snooze_suppresses_then_resurfaces(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        meta = session_end.load_focus_meta(vault)
        meta["projects"]["foo"] = {"last_worked_on": "2026-05-01"}
        session_end.save_focus_meta(vault, meta)
        # 49 days stale -> candidate; bar has no meta entry -> not a candidate.
        cands = session_end.compute_stale_candidates(vault, today=Date(2026, 6, 19))
        assert [c["slug"] for c in cands] == ["foo"]
        assert cands[0]["days_stale"] == 49
        # Snooze suppresses it.
        session_end.process_focus_updates(
            vault=vault, updates=session_end.FocusUpdates(snooze=["foo"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 6, 19),
        )
        assert session_end.compute_stale_candidates(vault, today=Date(2026, 6, 19)) == []
        # After the snooze window passes it resurfaces.
        assert [c["slug"] for c in session_end.compute_stale_candidates(vault, today=Date(2026, 7, 4))] == ["foo"]

    def test_move_to_complete_removes_from_meta(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        meta = session_end.load_focus_meta(vault)
        meta["projects"]["foo"] = {"last_worked_on": "2026-05-01"}
        session_end.save_focus_meta(vault, meta)
        session_end.process_focus_updates(
            vault=vault, updates=session_end.FocusUpdates(move_to_complete=["foo"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 6, 19),
        )
        assert "foo" not in session_end.load_focus_meta(vault)["projects"]

    def _add_backlog_project(self, vault, slug="parked"):
        focus = vault / "Context/current-focus.md"
        text = focus.read_text().replace(
            "## Complete",
            f"## Backlog\n\n### [[Work/Chalktalk/Projects/{slug}]]\n"
            "\U0001F4DA Reading backlog.\n\n## Complete",
        )
        focus.write_text(text)

    def test_backlog_swept_monthly_not_biweekly(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        self._add_backlog_project(vault)
        meta = session_end.load_focus_meta(vault)
        meta["projects"]["parked"] = {"last_worked_on": "2026-05-01"}
        session_end.save_focus_meta(vault, meta)
        # 20 days: past the active window (14) but inside the backlog
        # grooming window (30) -> not a candidate.
        assert session_end.compute_stale_candidates(vault, today=Date(2026, 5, 21)) == []
        # 49 days: due for grooming, tagged with its section.
        cands = session_end.compute_stale_candidates(vault, today=Date(2026, 6, 19))
        assert [(c["slug"], c["section"]) for c in cands] == [("parked", "backlog")]

    def test_snooze_defaults_per_section_and_stamps_last_asked_about(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        self._add_backlog_project(vault)
        meta = session_end.load_focus_meta(vault)
        meta["projects"]["foo"] = {"last_worked_on": "2026-05-01"}
        meta["projects"]["parked"] = {"last_worked_on": "2026-05-01"}
        session_end.save_focus_meta(vault, meta)
        session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(snooze=["foo", "parked"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 6, 19),
        )
        projects = session_end.load_focus_meta(vault)["projects"]
        # Active default = snooze_days (14); backlog keep-in-backlog default =
        # backlog_groom_days (30).
        assert projects["foo"]["snooze_until"] == "2026-07-03"
        assert projects["parked"]["snooze_until"] == "2026-07-19"
        # The ask is recorded, but last_worked_on is NOT stamped --
        # days_stale keeps accruing honestly.
        assert projects["foo"]["last_asked_about"] == "2026-06-19"
        assert projects["foo"]["last_worked_on"] == "2026-05-01"
        # Suppressed now, resurfaces after the snooze expires.
        assert session_end.compute_stale_candidates(vault, today=Date(2026, 7, 2)) == []
        assert [c["slug"] for c in session_end.compute_stale_candidates(vault, today=Date(2026, 7, 3))] == ["foo"]

    def test_snooze_accepts_custom_duration(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        meta = session_end.load_focus_meta(vault)
        meta["projects"]["foo"] = {"last_worked_on": "2026-05-01"}
        session_end.save_focus_meta(vault, meta)
        # "snooze for 3 weeks" -> {slug, days: 21}; YAML string form coerces.
        updates = session_end.FocusUpdates.model_validate(
            {"snooze": [{"slug": "foo", "days": 21}]}
        )
        session_end.process_focus_updates(
            vault=vault, updates=updates,
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 6, 19),
        )
        assert session_end.load_focus_meta(vault)["projects"]["foo"]["snooze_until"] == "2026-07-10"

    def test_move_to_active_promotes_backlog_block(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        self._add_backlog_project(vault)
        meta = session_end.load_focus_meta(vault)
        meta["projects"]["parked"] = {"last_worked_on": "2026-05-01", "snooze_until": "2026-06-01"}
        session_end.save_focus_meta(vault, meta)
        session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(move_to_active=["parked"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 6, 19),
        )
        text = (vault / "Context/current-focus.md").read_text()
        active_section = text.split("## Active Projects")[1].split("## Backlog")[0]
        backlog_section = text.split("## Backlog")[1].split("## Complete")[0]
        assert "Projects/parked]]" in active_section
        assert "\U0001F4DA Reading backlog." in active_section
        assert "Projects/parked]]" not in backlog_section
        entry = session_end.load_focus_meta(vault)["projects"]["parked"]
        assert entry["last_worked_on"] == "2026-06-19"
        assert "snooze_until" not in entry

    def test_stale_check_seeds_missing_entries(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        # foo and bar are Active but have no sidecar entries (added by hand).
        # Without seeding they are invisible to the sweep forever.
        assert session_end.compute_stale_candidates(vault, today=Date(2026, 6, 19)) == []
        assert "foo" not in session_end.load_focus_meta(vault).get("projects", {})
        # seed_missing (the --stale-check CLI path) stamps them with today.
        cands = session_end.compute_stale_candidates(
            vault, today=Date(2026, 6, 19), seed_missing=True
        )
        assert cands == []
        projects = session_end.load_focus_meta(vault)["projects"]
        assert projects["foo"]["last_worked_on"] == "2026-06-19"
        assert projects["bar"]["last_worked_on"] == "2026-06-19"


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

    def test_preflight_blocks_unaddressed_stale_project(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        meta = session_end.load_focus_meta(vault)
        meta["projects"] = {"foo": {"last_worked_on": "2026-03-01"}}
        session_end.save_focus_meta(vault, meta)
        manifest = session_end.SessionEndManifest(
            date="2026-05-09", topic="ok", tags=["session"],
            last_updated_slug="x", summary="x", projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x", learnings="x",
            files_modified=session_end.FilesModified(), next_steps="x",
        )
        problems = session_end.preflight_validate(
            manifest=manifest, vault=vault, org_name="Chalktalk",
            sections={"focus_updates"},
        )
        assert any("stale project 'foo'" in p for p in problems)

    def test_preflight_stale_gate_satisfied_by_snooze_or_retire(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        meta = session_end.load_focus_meta(vault)
        meta["projects"] = {
            "foo": {"last_worked_on": "2026-03-01"},
            "bar": {"last_worked_on": "2026-03-01"},
        }
        session_end.save_focus_meta(vault, meta)
        manifest = session_end.SessionEndManifest(
            date="2026-05-09", topic="ok", tags=["session"],
            last_updated_slug="x", summary="x", projects_touched=[],
            streams=[session_end.Stream(title="s", body="b")],
            key_decisions="x", learnings="x",
            files_modified=session_end.FilesModified(), next_steps="x",
            focus_updates=session_end.FocusUpdates(
                snooze=["foo"], move_to_retired=["bar"],
            ),
        )
        problems = session_end.preflight_validate(
            manifest=manifest, vault=vault, org_name="Chalktalk",
            sections={"focus_updates"},
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

    def _doc(self, vault, slug, body):
        p = vault / "Work/Chalktalk/Projects" / f"{slug}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {slug}\n\n{body}", encoding="utf-8")
        return p

    def test_warns_when_next_steps_replace_drops_other_threads(self, tmp_path, capsys):
        """A manifest written for one thread must not silently delete another's."""
        doc = self._doc(tmp_path, "multi-thread",
                        "## Next Steps\n- Permit occupancy question\n- Figma re-pull\n")
        upd = session_end.ProjectDocUpdate(
            slug="multi-thread", next_steps="- Sign the amendment"
        )
        session_end.append_to_project_doc(tmp_path, upd)
        err = capsys.readouterr().err
        assert "dropped 2 existing line(s)" in err
        assert "Permit occupancy question" in err
        assert "next_steps_replace_ok" in err

    def test_no_warning_when_replace_ok_is_set(self, tmp_path, capsys):
        self._doc(tmp_path, "p", "## Next Steps\n- Old item\n")
        upd = session_end.ProjectDocUpdate(
            slug="p", next_steps="- New item", next_steps_replace_ok=True
        )
        session_end.append_to_project_doc(tmp_path, upd)
        assert "dropped" not in capsys.readouterr().err

    def test_no_warning_when_existing_lines_are_preserved(self, tmp_path, capsys):
        """Merging the old bullets into the new body is the intended fix."""
        self._doc(tmp_path, "p", "## Next Steps\n- Keep me\n")
        upd = session_end.ProjectDocUpdate(
            slug="p", next_steps="- Keep me\n- And add this"
        )
        session_end.append_to_project_doc(tmp_path, upd)
        assert "dropped" not in capsys.readouterr().err

    def test_status_replace_never_warns(self, tmp_path, capsys):
        """Replacing a current-state line is exactly what `status` is for."""
        self._doc(tmp_path, "p", "## Status\n\U0001F7E2 Old status.\n")
        upd = session_end.ProjectDocUpdate(slug="p", status="\U0001F7E1 New status.")
        session_end.append_to_project_doc(tmp_path, upd)
        assert "dropped" not in capsys.readouterr().err

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
        assert "## Staging" in brag

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


class TestChangeReport:
    """Tests for per-file change report printed after a successful run."""

    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_session_log_change_report_includes_lines(self, tmp_path, capsys):
        """Full e2e run; stdout contains session log path with created (N lines)."""
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        # Session log path + created (N lines)
        assert "Sessions/2026-05/2026-05-09-full-example.md" in captured.out
        assert "created (" in captured.out
        assert "lines)" in captured.out

    def test_project_doc_structured_update_reports_each_op(self, tmp_path, capsys):
        """Structured update with all four fields; report has one line per section touched."""
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            status="🟢 **Active.** All good.",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="Hardening pass",
                body="- Fixed 5 bugs.",
            ),
            next_steps="- Deploy.\n- Tag release.",
            related_session="[[Sessions/2026-05/2026-05-09-test]] — test run",
        )
        rpt = session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        assert "## Status: replaced" in rpt.summary[0]
        assert any("## Recent activity: prepended 1 entry" in s for s in rpt.summary)
        assert any("## Next Steps: replaced" in s for s in rpt.summary)
        assert any("## Related Sessions: appended 1 wikilink" in s for s in rpt.summary)

    def test_recent_activity_trim_count_in_report(self, tmp_path):
        """Fixture has 2 entries; after prepending 1 more (total 3) no trim occurs.
        Then prepend a 4th; report says trimmed 1 oldest."""
        vault = self._setup_vault(tmp_path)
        proj = vault / "Work/Chalktalk/Projects/existing-project.md"
        # Add a 3rd entry so fixture has 3 total
        text = proj.read_text()
        text = text.replace(
            "## Recent activity\n\n### 2026-04-20",
            "## Recent activity\n\n### 2026-04-30 — Third\n- Third.\n\n### 2026-04-20",
        )
        proj.write_text(text)

        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            recent_activity=session_end.RecentActivityEntry(
                date="2026-05-09",
                title="Fourth causes trim",
                body="- Trimming now.",
            ),
        )
        rpt = session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        # The report should mention trimmed 1 oldest
        ra_lines = [s for s in rpt.summary if "Recent activity" in s]
        assert len(ra_lines) == 1
        assert "trimmed 1 oldest" in ra_lines[0]

    def test_decision_skipped_appears_in_report(self, tmp_path, capsys):
        """Pre-create a decision file; e2e run with that decision; report says skipped."""
        vault = self._setup_vault(tmp_path)
        # Pre-create the decision that the full manifest would write
        existing = vault / "Work/Chalktalk/Decisions/2026-05-09-test-decision.md"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("---\nexisting: true\n---\n")

        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Work/Chalktalk/Decisions/2026-05-09-test-decision.md" in captured.out
        assert "skipped (already exists)" in captured.out

    def test_focus_updates_report_lists_sections(self, tmp_path, capsys):
        """Full e2e run; report contains frontmatter bump and upserted projects."""
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "frontmatter last-updated:" in captured.out
        assert "## Active Projects: upserted" in captured.out

    def test_shipping_idempotent_skip_in_report(self, tmp_path, capsys):
        """Pre-write a matching bullet; helper run reports skipped (bullet already present)."""
        vault = self._setup_vault(tmp_path)
        entry = session_end.ShippingEntry(
            date="2026-05-09",
            label="pre-written thing",
            context="ctx",
        )
        # Pre-insert the exact bullet that the helper would write
        bullet = session_end.format_shipping_bullet(entry, "2026-05-09-test")
        log_path = vault / "Work/Chalktalk/Shipping Log.md"
        log_path.write_text(log_path.read_text() + bullet + "\n")

        rpt = session_end.append_to_shipping_log(
            vault=vault,
            entry=entry,
            session_log_filename="2026-05-09-test",
            org_name="Chalktalk",
        )
        assert "skipped (bullet already present)" in rpt.summary[0]

    def test_quiet_flag_suppresses_change_report(self, tmp_path, capsys):
        """With --quiet, per-file blocks are not printed but trailing summary is."""
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
            "--quiet",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        # Trailing summary always present
        assert "Wrote session-end artifacts under" in captured.out
        # Per-file path blocks NOT present
        assert "Sessions/2026-05/2026-05-09-full-example.md" not in captured.out
        assert "## Status:" not in captured.out
        assert "frontmatter last-updated:" not in captured.out

    def test_dry_run_does_not_emit_change_report(self, tmp_path, capsys):
        """--dry-run emits [dry-run] lines but NOT the change-report blocks."""
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
            "--dry-run",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        # dry-run preview lines are present
        assert "[dry-run]" in captured.out
        # Change report blocks are NOT present (no actual writes happened)
        assert "created (" not in captured.out
        assert "## Status: replaced" not in captured.out
        assert "frontmatter last-updated:" not in captured.out


class TestChangeReportPolish:
    """Polish: merge same-path blocks, suppress no-op last-updated, brag preview."""

    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_change_report_merges_same_path_blocks(self, tmp_path, capsys):
        """Two shipping entries to the same file print under one path heading."""
        vault = self._setup_vault(tmp_path)
        manifest_path = tmp_path / "m.yaml"
        manifest_path.write_text("""
date: 2026-05-09
topic: merge-test
tags: [session]
last_updated_slug: 2026-05-09-merge-test
summary: x
projects_touched: []
streams: [{title: x, body: x}]
key_decisions: x
learnings: x
files_modified: {}
next_steps: x
extractions:
  shipping_log:
    - { date: 2026-05-09, label: First thing, context: ctx1 }
    - { date: 2026-05-09, label: Second thing, context: ctx2 }
""")
        rc = session_end.main([
            "--manifest", str(manifest_path),
            "--vault-path", str(vault),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        # Path appears exactly once at column 0 (start of line) followed by indented summaries.
        out = captured.out
        path_count = sum(
            1 for line in out.splitlines()
            if line == "Work/Chalktalk/Shipping Log.md"
        )
        assert path_count == 1, f"expected path once, saw {path_count} times in:\n{out}"
        # Both bullet lines indented under it (first creates the heading; second appends)
        # New diff format: header line + "+ <full bullet content>" line per op
        assert "## 2026-05: heading created; prepended 1 bullet" in out
        assert "## 2026-05: prepended 1 bullet" in out
        # Full bullet content shown on "+ " lines
        assert "+ - **2026-05-09** — First thing — ctx1." in out
        assert "+ - **2026-05-09** — Second thing — ctx2." in out

    def test_change_report_skips_noop_last_updated(self, tmp_path, capsys):
        """When last-updated slug already matches, no frontmatter line in report."""
        vault = self._setup_vault(tmp_path)
        # Pre-set the fixture's last-updated to match what we'll send
        focus_path = vault / "Context/current-focus.md"
        text = focus_path.read_text()
        text = text.replace(
            "last-updated: 2026-04-30-old-session",
            "last-updated: 2026-05-09-noop-test",
        )
        focus_path.write_text(text)

        rpt = session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(),
            last_updated_slug="2026-05-09-noop-test",
            org_name="Chalktalk",
        )
        assert not any("frontmatter last-updated:" in s for s in rpt.summary), (
            f"expected no frontmatter line, got: {rpt.summary}"
        )

    def test_change_report_emits_last_updated_line_when_changed(self, tmp_path):
        """When slug differs, frontmatter line IS in report with old to new."""
        vault = self._setup_vault(tmp_path)
        rpt = session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(),
            last_updated_slug="2026-05-09-new-session",
            org_name="Chalktalk",
        )
        assert any(
            "frontmatter last-updated: 2026-04-30-old-session to 2026-05-09-new-session"
            in s for s in rpt.summary
        ), f"expected old-to-new line, got: {rpt.summary}"

    def test_brag_change_report_includes_full_body_in_diff(self, tmp_path):
        """Brag append's report shows the full bullet line (no truncation) on a + line."""
        vault = self._setup_vault(tmp_path)
        entry = session_end.BragEntry(
            date="2026-05-09",
            body="did the thing",
        )
        rpt = session_end.append_to_brag_doc(
            vault=vault, entry=entry, session_log_filename="2026-05-09-test",
        )
        # Header line names the op, "+ " line carries full bullet content
        assert any(s.startswith("## Staging:") and "1 entry" in s for s in rpt.summary), (
            f"expected header line, got: {rpt.summary}"
        )
        assert any(
            s.startswith("+ ") and "did the thing" in s for s in rpt.summary
        ), f"expected + line with full body, got: {rpt.summary}"

    def test_brag_change_report_shows_full_body_no_truncation(self, tmp_path):
        """Long bodies appear in full on the + line (no 60-char truncation in diff format)."""
        vault = self._setup_vault(tmp_path)
        long_body = "x" * 100
        entry = session_end.BragEntry(
            date="2026-05-09",
            body=long_body,
        )
        rpt = session_end.append_to_brag_doc(
            vault=vault, entry=entry, session_log_filename="2026-05-09-test",
        )
        # Full 100-char body should appear verbatim on a + line, no "..." truncation
        plus_lines = [s for s in rpt.summary if s.startswith("+ ")]
        joined = "\n".join(plus_lines)
        assert ("x" * 100) in joined, f"expected full 100-char body, got: {plus_lines}"
        assert "..." not in joined, f"expected no truncation, got: {plus_lines}"


class TestUnifiedDiffFormat:
    """The change report shows full content with '- ' for removed and '+ ' for added lines."""

    def _setup_vault(self, tmp_path):
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_status_replace_shows_old_and_new_content(self, tmp_path):
        """Status replace emits '- <old>' lines AND '+ <new>' lines."""
        vault = self._setup_vault(tmp_path)
        update = session_end.ProjectDocUpdate(
            slug="existing-project",
            status="🟢 Brand new status line.",
        )
        rpt = session_end.append_to_project_doc(vault=vault, update=update, org_name="Chalktalk")
        minus_lines = [s for s in rpt.summary if s.startswith("- ")]
        plus_lines = [s for s in rpt.summary if s.startswith("+ ")]
        assert minus_lines, f"expected at least one '- ' removed line, got: {rpt.summary}"
        assert plus_lines, f"expected at least one '+ ' added line, got: {rpt.summary}"
        assert any("🟢 Brand new status line." in s for s in plus_lines), (
            f"expected new status text on + line, got: {plus_lines}"
        )

    def test_focus_upsert_replace_shows_old_block_removed_and_new_added(self, tmp_path):
        """Upsert against an existing slug emits both old block and new block."""
        vault = self._setup_vault(tmp_path)
        rpt = session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(
                upsert=[session_end.FocusUpsert(slug="foo", status_line="**🔴 Now blocked.** Reason here.")],
            ),
            last_updated_slug="2026-05-09-test",
            org_name="Chalktalk",
        )
        minus_lines = [s for s in rpt.summary if s.startswith("- ")]
        plus_lines = [s for s in rpt.summary if s.startswith("+ ")]
        assert any("Foo is active" in s for s in minus_lines), (
            f"expected old foo block on - lines, got: {minus_lines}"
        )
        assert any("🔴 Now blocked" in s for s in plus_lines), (
            f"expected new status_line on + lines, got: {plus_lines}"
        )

    def test_focus_remove_shows_only_minus_lines(self, tmp_path):
        """Pure remove emits '- ' lines for the deleted block, no '+ ' lines."""
        vault = self._setup_vault(tmp_path)
        rpt = session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(remove=["foo"]),
            last_updated_slug="2026-05-09-test",
            org_name="Chalktalk",
        )
        # Find the section about the remove (skip frontmatter bump if present)
        remove_idx = next(
            i for i, s in enumerate(rpt.summary) if s.startswith("removed: foo")
        )
        # Lines after the header, before any next header (no header here, all minus to end of slice)
        diff_lines = [s for s in rpt.summary[remove_idx + 1:] if s.startswith(("- ", "+ "))]
        assert diff_lines, f"expected diff lines after remove header, got: {rpt.summary}"
        assert all(s.startswith("- ") for s in diff_lines[:2]), (
            f"expected first lines after 'removed:' to be '- ' lines, got: {diff_lines}"
        )

    def test_focus_move_to_complete_shows_old_and_new_with_checkmark(self, tmp_path):
        """move_to_complete shows old block (no checkmark) on - lines and new block (with checkmark) on + lines."""
        vault = self._setup_vault(tmp_path)
        rpt = session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(move_to_complete=["foo"]),
            last_updated_slug="2026-05-09-test",
            org_name="Chalktalk",
        )
        minus_lines = [s for s in rpt.summary if s.startswith("- ")]
        plus_lines = [s for s in rpt.summary if s.startswith("+ ")]
        # Old block heading appears in - lines (no checkmark)
        assert any(
            "[[Work/Chalktalk/Projects/foo]]" in s and "✅" not in s
            for s in minus_lines
        ), f"expected old block (no checkmark) on - lines, got: {minus_lines}"
        # New block heading appears in + lines (with checkmark)
        assert any(
            "[[Work/Chalktalk/Projects/foo]] ✅" in s for s in plus_lines
        ), f"expected new block with ✅ on + lines, got: {plus_lines}"

    def test_shipping_prepend_shows_full_bullet_on_plus_line(self, tmp_path):
        """Shipping append shows the full bullet (no 60-char truncation) on a + line."""
        vault = self._setup_vault(tmp_path)
        long_label = "y" * 80
        entry = session_end.ShippingEntry(
            date="2026-05-09",
            label=long_label,
            context="ctx",
        )
        rpt = session_end.append_to_shipping_log(
            vault=vault,
            entry=entry,
            session_log_filename="2026-05-09-test",
            org_name="Chalktalk",
        )
        plus_lines = [s for s in rpt.summary if s.startswith("+ ")]
        joined = "\n".join(plus_lines)
        assert ("y" * 80) in joined, f"expected full 80-char label verbatim, got: {plus_lines}"
        assert "..." not in joined, f"expected no truncation, got: {plus_lines}"


class TestCreatedFilePreview:
    """Preview substantive content of newly-created session-log and decision files."""

    def _setup_vault(self, tmp_path):
        import shutil
        vault = tmp_path / "vault"
        fixtures = Path(__file__).parent / "fixtures" / "vault"
        shutil.copytree(fixtures, vault)
        return vault

    def test_session_log_preview_emits_summary_and_first_stream(self, tmp_path, capsys):
        """Default run prints + lines from the session log's Summary and first stream."""
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
        ])
        assert rc == 0
        out = capsys.readouterr().out

        session_block_start = out.index("Sessions/2026-05/2026-05-09-full-example.md")
        next_block_idx = out.find("\n\n", session_block_start + 1)
        session_block = out[session_block_start:next_block_idx if next_block_idx != -1 else len(out)]

        assert "+ Full-coverage manifest for end-to-end testing." in session_block, (
            f"expected summary preview line in session-log block, got:\n{session_block}"
        )
        assert "+ ### Stream 1: Did stuff" in session_block, (
            f"expected first-stream heading preview line, got:\n{session_block}"
        )
        assert "+ Body of stream 1." in session_block, (
            f"expected first-stream body preview line, got:\n{session_block}"
        )

    def test_decision_file_preview_emits_chosen_and_reasoning(self, tmp_path, capsys):
        """Default run prints + lines from the decision's Chosen and Reasoning sections."""
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
        ])
        assert rc == 0
        out = capsys.readouterr().out

        decision_block_start = out.index("Work/Chalktalk/Decisions/2026-05-09-test-decision.md")
        next_block_idx = out.find("\n\n", decision_block_start + 1)
        decision_block = out[decision_block_start:next_block_idx if next_block_idx != -1 else len(out)]

        assert "+ ## Chosen" in decision_block
        assert "+ **A**" in decision_block
        assert "+ ## Reasoning" in decision_block
        assert "+ - Clearer." in decision_block

    def test_quiet_suppresses_created_file_preview(self, tmp_path, capsys):
        """--quiet hides per-file blocks entirely — including the new content preview."""
        vault = self._setup_vault(tmp_path)
        manifest_src = Path(__file__).parent / "fixtures" / "manifest_full.yaml"
        rc = session_end.main([
            "--manifest", str(manifest_src),
            "--vault-path", str(vault),
            "--quiet",
        ])
        assert rc == 0
        out = capsys.readouterr().out

        assert "+ Full-coverage manifest for end-to-end testing." not in out
        assert "+ ### Stream 1: Did stuff" not in out
        assert "+ ## Chosen" not in out
        assert "+ **A**" not in out

    def test_preview_ignores_h2_inside_decision_code_fence(self, tmp_path):
        """`## ` lines inside a fenced code block must NOT end the Chosen section."""
        vault = tmp_path / "vault"
        p = vault / "Work/Chalktalk/Decisions/2026-05-09-d.md"
        p.parent.mkdir(parents=True)
        p.write_text(
            "## Chosen\nfirst paragraph\n"
            "```md\n"
            "## not actually a heading, just code\n"
            "### still code\n"
            "```\n"
            "after code\n\n"
            "## Reasoning\nbecause\n"
        )
        preview = session_end._created_file_preview(
            vault, "Work/Chalktalk/Decisions/2026-05-09-d.md"
        )
        assert "after code" in preview, (
            f"`after code` should be in preview; fence-unaware parser dropped it. Got: {preview}"
        )
        assert "## Reasoning" in preview
        assert "because" in preview

    def test_preview_ignores_h3_inside_stream_code_fence(self, tmp_path):
        """`### ` lines inside a fenced code block must NOT end the first stream."""
        vault = tmp_path / "vault"
        p = vault / "Sessions/2026-05/2026-05-09-x.md"
        p.parent.mkdir(parents=True)
        p.write_text(
            "---\ndate: 2026-05-09\n---\n\n"
            "## Summary\nsummary line\n\n"
            "## What We Did\n\n"
            "### Stream 1\n"
            "intro\n"
            "```python\n"
            "# code containing ### marker that should NOT terminate stream\n"
            "x = 1\n"
            "```\n"
            "more body after fence\n"
        )
        preview = session_end._created_file_preview(
            vault, "Sessions/2026-05/2026-05-09-x.md"
        )
        assert "more body after fence" in preview, (
            f"post-fence body must survive; got: {preview}"
        )
        assert "```python" in preview

    def test_created_file_preview_caps_at_60_lines_with_trailer(self, tmp_path):
        """When the previewed content exceeds 60 lines, output is capped + trailer added."""
        vault = tmp_path / "vault"
        sessions_dir = vault / "Sessions" / "2026-05"
        sessions_dir.mkdir(parents=True)
        long_summary_body = "\n".join(f"line {i}" for i in range(120))
        session_file = sessions_dir / "2026-05-09-long.md"
        session_file.write_text(
            "---\ndate: 2026-05-09\n---\n\n"
            "# Session: long\n\n"
            "## Summary\n"
            f"{long_summary_body}\n\n"
            "## What We Did\n\n"
            "### Only stream\n"
            "irrelevant for cap test\n"
        )

        preview = session_end._created_file_preview(vault, "Sessions/2026-05/2026-05-09-long.md")
        assert len(preview) == 61, f"expected 60 content lines + 1 trailer, got {len(preview)}"
        assert preview[-1].startswith("... (")
        assert "more lines in file" in preview[-1]
        assert "line 0" in preview
        assert "line 59" in preview
        assert "line 60" not in preview


class TestSeeAlsoCrossLinks:
    """`see_also` wikilinks render as ` · See [[link]]` after the session back-link."""

    def test_shipping_entry_with_one_see_also(self):
        entry = session_end.ShippingEntry(
            date="2026-05-09",
            label="thing shipped",
            context="ctx",
            see_also=["[[Work/Chalktalk/Decisions/2026-05-09-foo]]"],
        )
        bullet = session_end.format_shipping_bullet(entry, "2026-05-09-test")
        assert bullet == (
            "- **2026-05-09** — thing shipped — ctx. "
            "[[Sessions/2026-05/2026-05-09-test]] "
            "· See [[Work/Chalktalk/Decisions/2026-05-09-foo]]"
        )

    def test_brag_entry_with_two_see_also_preserves_order(self):
        entry = session_end.BragEntry(
            date="2026-05-09",
            body="did the exceptional thing",
            see_also=[
                "[[Work/Chalktalk/Decisions/2026-05-09-foo]]",
                "[[Work/Chalktalk/Knowledge/skill-runtime-antipatterns]]",
            ],
        )
        bullet = session_end.format_brag_bullet(entry, "2026-05-09-test")
        assert bullet == (
            "- **2026-05-09** — did the exceptional thing. "
            "[[Sessions/2026-05/2026-05-09-test]] "
            "· See [[Work/Chalktalk/Decisions/2026-05-09-foo]] "
            "· See [[Work/Chalktalk/Knowledge/skill-runtime-antipatterns]]"
        )

    def test_empty_see_also_matches_pre_field_format(self):
        """Regression guard: with no see_also, the bullet is identical to old output."""
        ship = session_end.ShippingEntry(
            date="2026-05-09", label="thing", context="ctx",
        )
        ship_bullet = session_end.format_shipping_bullet(ship, "2026-05-09-test")
        assert ship_bullet == (
            "- **2026-05-09** — thing — ctx. "
            "[[Sessions/2026-05/2026-05-09-test]]"
        )

        brag = session_end.BragEntry(
            date="2026-05-09", body="did the thing",
        )
        brag_bullet = session_end.format_brag_bullet(brag, "2026-05-09-test")
        assert brag_bullet == (
            "- **2026-05-09** — did the thing. "
            "[[Sessions/2026-05/2026-05-09-test]]"
        )

    def test_malformed_see_also_wikilink_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc:
            session_end.ShippingEntry(
                date="2026-05-09",
                label="thing",
                see_also=["not-a-wikilink"],
            )
        assert "see_also" in str(exc.value)

        with pytest.raises(ValidationError):
            session_end.BragEntry(
                date="2026-05-09",
                body="did",
                see_also=["[[bad nested [[brackets]]]]"],
            )

    def test_see_also_rejects_embedded_newlines_multipipe_whitespace(self):
        """Hardened validator rejects classes of malformed wikilinks (audit-fix)."""
        from pydantic import ValidationError

        bad_cases = [
            "[[A|line1\nline2]]",       # newline in alias splits the bullet
            "[[A\nB]]",                 # newline in target splits the bullet
            "[[A|b|c]]",                # multiple pipes
            "[[   ]]",                  # whitespace-only target
            "[[A|   ]]",                # whitespace-only alias
            "[[ A]]",                   # leading whitespace
            "[[A| ]]",                  # trailing whitespace alias
            "[[]]",                     # empty target
        ]
        for v in bad_cases:
            with pytest.raises(ValidationError, match="see_also"):
                session_end.ShippingEntry(date="2026-05-09", label="x", see_also=[v])

    def test_see_also_accepts_common_obsidian_wikilink_forms(self):
        """Real Obsidian forms — paths, #headings, |aliases, paths with spaces — pass."""
        good_cases = [
            "[[A]]",
            "[[Work/Chalktalk/Decisions/2026-05-09-foo]]",
            "[[Work/Chalktalk/Decisions/foo|Display Name]]",
            "[[Work/Chalktalk/Decisions/foo#Section]]",
            "[[Work/Chalktalk/Decisions/foo#Section|Display]]",
            "[[Personal/Projects/InBloom Early Learning/overview]]",
        ]
        for v in good_cases:
            entry = session_end.ShippingEntry(
                date="2026-05-09", label="x", see_also=[v],
            )
            assert entry.see_also == [v]


class TestRefreshQmdIndex:
    """Best-effort vault re-index wired into the save ritual. Contract: never
    raises, never depends on qmd being installed, runs update then embed."""

    def test_noop_when_qmd_absent(self, monkeypatch):
        monkeypatch.setattr(session_end.shutil, "which", lambda _: None)
        called = []
        monkeypatch.setattr(
            session_end.subprocess, "run", lambda *a, **k: called.append(a)
        )
        session_end.refresh_qmd_index(quiet=True)  # must not raise
        assert called == []  # qmd never invoked

    def test_runs_update_then_embed_when_present(self, monkeypatch):
        monkeypatch.setattr(session_end.shutil, "which", lambda _: "/usr/bin/qmd")
        calls = []
        monkeypatch.setattr(
            session_end.subprocess, "run", lambda cmd, **k: calls.append(cmd)
        )
        session_end.refresh_qmd_index(quiet=True)
        assert calls == [["qmd", "update"], ["qmd", "embed"]]

    def test_reindex_failure_is_swallowed(self, monkeypatch):
        """A reindex failure must never propagate — the save already succeeded."""
        monkeypatch.setattr(session_end.shutil, "which", lambda _: "/usr/bin/qmd")

        def boom(*a, **k):
            raise OSError("simulated qmd crash")

        monkeypatch.setattr(session_end.subprocess, "run", boom)
        session_end.refresh_qmd_index(quiet=True)  # must not raise


# ---------------------------------------------------------------------------
# Nested work project slugs (Projects/<Folder>/<slug>)
#
# Added 2026-07-27 after a vault consolidation moved several project docs under
# Work/<org>/Projects/Content/. The helper rejected every nested slug, so those
# project docs and the current-focus upsert had to be written by hand. Every
# write site already does mkdir(parents=True) and every path/wikilink is
# f-string interpolated, so only the validator needed widening.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", [
    "curriculum-synthesis-skill",          # flat - the pre-existing case, must still pass
    "a",
    "Content/curriculum-synthesis-skill",  # one folder segment
    "Content/lesson-production/index",     # two folder segments
    "Some Folder/nested-doc",              # spaces are legal in a folder segment
])
def test_work_slug_accepts_flat_and_nested(slug):
    assert session_end._validate_slug_for_category(slug, "work") == slug


@pytest.mark.parametrize("slug", [
    "../etc/passwd",     # path traversal
    "Content/../../x",
    "/leading",
    "trailing/",
    "double//slash",
    "Content/",
    "Content/UPPER",     # final segment must stay kebab-case (it becomes a filename)
    "has space",         # ...and may not contain spaces
])
def test_work_slug_rejects_unsafe_or_malformed(slug):
    with pytest.raises(ValueError):
        session_end._validate_slug_for_category(slug, "work")


def test_project_doc_path_handles_nested_work_slug():
    assert session_end.project_doc_path(
        "Content/curriculum-synthesis-skill", "work", "Chalktalk"
    ) == "Work/Chalktalk/Projects/Content/curriculum-synthesis-skill.md"
    # flat slugs are unchanged
    assert session_end.project_doc_path(
        "renewal-storytelling", "work", "Chalktalk"
    ) == "Work/Chalktalk/Projects/renewal-storytelling.md"


def test_personal_slug_still_forbids_slash():
    """Personal slugs become a DIRECTORY name (Personal/Projects/<slug>/overview.md),
    so '/' stays illegal there even though work slugs now allow it."""
    with pytest.raises(ValueError):
        session_end._validate_slug_for_category("Some/Nested", "personal")
    assert session_end._validate_slug_for_category("InBloom Early Learning", "personal")


def test_nested_slug_round_trips_through_a_new_project_doc(tmp_path):
    """End-to-end: a nested slug creates the parent folder and lands at the right path."""
    doc = session_end.NewProjectDoc(
        slug="Content/brand-new-thing",
        frontmatter={"type": "project", "status": "active"},
        body="# Brand new thing\n\nBody.",
    )
    report = session_end.write_new_project_doc(tmp_path, doc, org_name="Chalktalk")
    written = tmp_path / "Work/Chalktalk/Projects/Content/brand-new-thing.md"
    assert written.is_file(), f"expected {written}"
    assert report.path == "Work/Chalktalk/Projects/Content/brand-new-thing.md"


# ---------------------------------------------------------------------------
# Task 7: the KNOWLEDGE extraction bucket
# ---------------------------------------------------------------------------

from pydantic import ValidationError


class TestKnowledgeNotes:
    def _note(self, **kw):
        base = dict(
            slug="nine-layers-map",
            title="The nine-layers map",
            summary="Where each kind of content-system improvement lives.",
            body="| layer | what exists |\n|---|---|\n| 1 | gates |",
            source_files=["10-projects/2026-08-review-pipeline-one-reviewer-per-layer/layers-map-2026-08-20.md"],
        )
        base.update(kw)
        return session_end.KnowledgeNote(**base)

    def test_path_work_and_personal(self):
        assert session_end.knowledge_note_path(self._note(), "Chalktalk") == "Work/Chalktalk/Knowledge/nine-layers-map.md"
        assert session_end.knowledge_note_path(self._note(category="personal"), "Chalktalk") == "Personal/Knowledge/nine-layers-map.md"

    def test_render_carries_type_category_provenance(self):
        text = session_end.render_knowledge_note(self._note(), "[[Sessions/2026-09/2026-09-05-x]]", Date(2026, 9, 5))
        assert text.startswith("---\ntype: knowledge\n")
        assert "category: work" in text and "created: 2026-09-05" in text
        assert "# The nine-layers map" in text and "## Provenance" in text
        assert "[[Sessions/2026-09/2026-09-05-x]]" in text and "layers-map-2026-08-20.md" in text

    def test_write_creates_and_skips_collision(self, tmp_path):
        r1 = session_end.write_knowledge_notes(tmp_path, [self._note()], Date(2026, 9, 5), "2026-09-05-x", "Chalktalk")
        assert r1[0].summary == ["created"] and (tmp_path / "Work/Chalktalk/Knowledge/nine-layers-map.md").exists()
        r2 = session_end.write_knowledge_notes(tmp_path, [self._note(title="changed")], Date(2026, 9, 5), "2026-09-05-x", "Chalktalk")
        assert r2[0].summary == ["skipped (already exists)"]
        assert "changed" not in (tmp_path / "Work/Chalktalk/Knowledge/nine-layers-map.md").read_text()

    def test_write_batch_partial_collision_still_writes_the_rest(self, tmp_path):
        """A mutant that abandons the WHOLE batch when any single note collides (returns early
        or raises instead of skip-and-continue) would pass every other Knowledge test here,
        because both other write_knowledge_notes calls use one-item lists. A two-item batch with
        one colliding slug and one fresh slug is the one that catches it."""
        r1 = session_end.write_knowledge_notes(tmp_path, [self._note()], Date(2026, 9, 5), "2026-09-05-x", "Chalktalk")
        assert r1[0].summary == ["created"]
        r2 = session_end.write_knowledge_notes(
            tmp_path,
            [self._note(), self._note(slug="second-note", title="Second note")],
            Date(2026, 9, 5), "2026-09-05-y", "Chalktalk",
        )
        assert r2[0].summary == ["skipped (already exists)"]
        assert r2[1].summary == ["created"]
        assert (tmp_path / "Work/Chalktalk/Knowledge/second-note.md").exists()

    def test_slug_must_be_kebab(self):
        with pytest.raises(ValidationError):
            self._note(slug="Nine Layers")

    def test_preflight_flags_same_run_collision(self, tmp_path):
        m = session_end.SessionEndManifest(date=Date(2026, 9, 5), topic="t", tags=["t"], last_updated_slug="2026-09-05-t",
            summary="s", projects_touched=[session_end.ProjectTouched(slug="foo", note="n")],
            streams=[session_end.Stream(title="a", body="b")], key_decisions="-", learnings="-",
            files_modified=session_end.FilesModified(), next_steps="-",
            extractions=session_end.Extractions(knowledge=[self._note(), self._note(title="dup")]))
        problems = session_end.preflight_validate(m, tmp_path, "Chalktalk", {"extractions"})
        assert any("extractions.knowledge" in p for p in problems)


# ---------------------------------------------------------------------------
# Amendment 2026-09-06: the ARTIFACTS extraction bucket (session-end half)
# ---------------------------------------------------------------------------

class TestArtifactsBucket:
    def _entry(self, **kw):
        base = dict(
            title="The nine-layers map",
            url="https://claude.ai/public/artifacts/abc123",
            date=Date(2026, 9, 5),
            account="mohannad@chalktalk.academy",
            project="memory-and-workspace-system",
            source="10-projects/2026-09-memory-and-workspace-system/scratch/nine-layers-map.html",
        )
        base.update(kw)
        return session_end.ArtifactEntry(**base)

    def test_append_creates_note(self, tmp_path):
        reports = session_end.append_to_artifacts_note(tmp_path, [self._entry()], "2026-09-05-x")
        note = tmp_path / "Context/artifacts.md"
        assert note.exists()
        text = note.read_text()
        assert "| date | title | url | account | project | source | session |" in text
        assert "The nine-layers map" in text
        assert reports[0].summary == ["created"]

    def test_second_run_same_row_appends_nothing(self, tmp_path):
        session_end.append_to_artifacts_note(tmp_path, [self._entry()], "2026-09-05-x")
        note = tmp_path / "Context/artifacts.md"
        before = note.read_text()
        r2 = session_end.append_to_artifacts_note(tmp_path, [self._entry()], "2026-09-05-x")
        after = note.read_text()
        assert before == after
        assert r2[0].summary == ["skipped (already exists)"]

    def test_project_none_renders(self, tmp_path):
        session_end.append_to_artifacts_note(tmp_path, [self._entry(project="none")], "2026-09-05-x")
        text = (tmp_path / "Context/artifacts.md").read_text()
        assert "| none |" in text

    def test_second_run_different_row_still_appends(self, tmp_path):
        """The dedup key is the exact row TEXT, not merely whether the note file already
        exists. A mutant that skips appending whenever Context/artifacts.md is already present
        (regardless of the row) would pass every other Artifacts test here — none of them call
        the writer twice with different entries — so this is the one that catches it."""
        session_end.append_to_artifacts_note(tmp_path, [self._entry(title="First artifact")], "2026-09-05-x")
        r2 = session_end.append_to_artifacts_note(
            tmp_path, [self._entry(title="Second artifact", url="https://claude.ai/public/artifacts/def456")],
            "2026-09-05-y",
        )
        text = (tmp_path / "Context/artifacts.md").read_text()
        assert "First artifact" in text
        assert "Second artifact" in text
        assert r2[0].summary == ["appended"]


# ---------------------------------------------------------------------------
# Task 8: the staleness sweep moves the container folder
# ---------------------------------------------------------------------------

class TestContainerMove:
    def test_folder_slug_forms(self):
        assert session_end.folder_slug("Content/lesson-production/index") == "lesson-production"
        assert session_end.folder_slug("InBloom Early Learning") == "inbloom-early-learning"
        assert session_end.folder_slug("Personal/Projects/figma-to-site/overview") == "figma-to-site"
        assert session_end.folder_slug("rules-catalog-system") == "rules-catalog-system"

    def test_find_containers_matches_dated_project_and_area(self, tmp_path):
        (tmp_path / "10-projects/2026-08-rules-catalog-system").mkdir(parents=True)
        (tmp_path / "10-projects/rules-catalog-system").mkdir(parents=True)   # undated: NOT a project folder
        (tmp_path / "20-areas/outreach-playbook").mkdir(parents=True)
        assert [d.name for d in session_end.find_containers(tmp_path, "rules-catalog-system")] == ["2026-08-rules-catalog-system"]
        assert [d.name for d in session_end.find_containers(tmp_path, "outreach-playbook")] == ["outreach-playbook"]
        assert session_end.find_containers(tmp_path, "nothing-here") == []

    def test_two_folders_for_one_slug_is_a_preflight_failure(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        ws = tmp_path / "ws"; (ws / "10-projects/2026-07-foo").mkdir(parents=True); (ws / "10-projects/2026-08-foo").mkdir(parents=True)
        problems = session_end.preflight_validate(self._manifest_moving("foo"), vault, "Chalktalk", {"focus_updates"}, workspace=ws)
        assert any("more than one folder" in p for p in problems)

    def test_recently_written_container_is_a_preflight_failure(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        ws = tmp_path / "ws"; d = ws / "10-projects/2026-08-foo"; d.mkdir(parents=True); (d / "live.md").write_text("# being edited now")
        problems = session_end.preflight_validate(self._manifest_moving("foo"), vault, "Chalktalk", {"focus_updates"}, workspace=ws)
        assert any("written in the last" in p for p in problems)

    def _setup_vault(self, tmp_path):
        # Same fixture copy the existing focus tests use: fixtures/vault has a project `foo` under Active.
        vault = tmp_path / "vault"; shutil.copytree(Path(__file__).parent / "fixtures" / "vault", vault); return vault

    def test_move_to_complete_archives_the_container(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        ws = tmp_path / "ws pace"; (ws / "10-projects/2026-08-foo/done").mkdir(parents=True)
        (ws / "10-projects/2026-08-foo/notes.md").write_text("# n")
        import os, time; old = time.time() - 3600
        for p in (ws / "10-projects/2026-08-foo").rglob("*"): os.utime(p, (old, old))
        rpt = session_end.process_focus_updates(vault=vault, updates=session_end.FocusUpdates(move_to_complete=["foo"]),
            last_updated_slug="2026-09-05-x", org_name="Chalktalk", workspace=ws)
        assert (ws / "90-archive/projects/2026-08-foo/notes.md").exists()
        assert not (ws / "10-projects/2026-08-foo").exists()
        assert any("90-archive/projects/2026-08-foo" in s for s in rpt.summary)

    def test_retire_without_a_folder_reports_and_continues(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        ws = tmp_path / "ws"; (ws / "10-projects").mkdir(parents=True)
        rpt = session_end.process_focus_updates(vault=vault, updates=session_end.FocusUpdates(move_to_retired=["foo"]),
            last_updated_slug="2026-09-05-x", org_name="Chalktalk", workspace=ws)
        assert any("no container folder" in s for s in rpt.summary)

    def _manifest_moving(self, slug):
        return session_end.SessionEndManifest(date=Date(2026, 9, 5), topic="t", tags=["t"], last_updated_slug="2026-09-05-t",
            summary="s", projects_touched=[session_end.ProjectTouched(slug=slug, note="n")],
            streams=[session_end.Stream(title="a", body="b")], key_decisions="-", learnings="-",
            files_modified=session_end.FilesModified(), next_steps="-",
            focus_updates=session_end.FocusUpdates(move_to_complete=[slug]))

    def test_preflight_refuses_when_destination_exists(self, tmp_path):
        vault = self._setup_vault(tmp_path)
        ws = tmp_path / "ws"; (ws / "10-projects/2026-08-foo").mkdir(parents=True); (ws / "90-archive/projects/2026-08-foo").mkdir(parents=True)
        import os, time; old = time.time() - 3600; os.utime(ws / "10-projects/2026-08-foo", (old, old))
        problems = session_end.preflight_validate(self._manifest_moving("foo"), vault, "Chalktalk", {"focus_updates"}, workspace=ws)
        assert any("90-archive/projects/2026-08-foo already exists" in p for p in problems)

    def test_folder_move_happens_before_the_vault_write_even_if_the_write_then_fails(self, tmp_path, monkeypatch):
        """The ordering guarantee -- folder move before any vault write -- is the binding
        constraint the whole feature rests on. A fully successful run looks IDENTICAL whether the
        folder moves first or the vault writes first, so swapping the two operations would leave
        every other test in this file green. This test forces the vault write to fail (patches
        Path.write_text, which both the current-focus.md edit and the .focus-meta.json sidecar
        save go through) and asserts the container folder has ALREADY moved to 90-archive/projects
        by the time the failure surfaces, while current-focus.md on disk is untouched."""
        vault = self._setup_vault(tmp_path)
        ws = tmp_path / "ws"; (ws / "10-projects/2026-08-foo/done").mkdir(parents=True)
        (ws / "10-projects/2026-08-foo/notes.md").write_text("# n")
        import os, time; old = time.time() - 3600
        for p in (ws / "10-projects/2026-08-foo").rglob("*"): os.utime(p, (old, old))

        before_focus = (vault / "Context/current-focus.md").read_text()

        def _boom(self, *a, **kw):
            raise RuntimeError("simulated vault-write failure")
        monkeypatch.setattr(Path, "write_text", _boom)

        with pytest.raises(RuntimeError, match="simulated vault-write failure"):
            session_end.process_focus_updates(
                vault=vault, updates=session_end.FocusUpdates(move_to_complete=["foo"]),
                last_updated_slug="2026-09-05-x", org_name="Chalktalk", workspace=ws,
            )

        assert (ws / "90-archive/projects/2026-08-foo/notes.md").exists()
        assert not (ws / "10-projects/2026-08-foo").exists()
        assert (vault / "Context/current-focus.md").read_text() == before_focus
