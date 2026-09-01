"""Slug extraction must agree with block resolution, for every heading shape.

The sweep derives a slug from each `### [[...]]` heading in current-focus.md;
`focus_updates` later resolves that slug back to the same heading. Those two
halves are written independently, and when they disagree the failure is silent:
the manifest passes preflight, the markdown is never touched, and the sidecar
entry is dropped, so the project stops being swept with nothing in the change
report to say so.

The property test below is the guard: whatever the extractor emits, the
resolver must find. It is asserted over every heading in the fixture rather
than a list of slugs, so a new heading shape is covered the day it is added.
"""

from datetime import date as Date

import session_end


# One heading of every shape that occurs in a real current-focus.md.
FOCUS = """---
last-updated: 2026-08-01-x
---

# Current Focus

## Active Projects

### [[Work/Chalktalk/Projects/flat-project]]
🟢 A flat work project.

### [[Work/Chalktalk/Projects/Content/lesson-production/index]]
🟢 A nested work project.

### [[Work/Chalktalk/Projects/Content/curriculum-creation-sop]]
🟢 A sibling under the same parent directory.

### [[Work/Chalktalk/Projects/aliased-project|Customer Journey and Implementation/CX]]
🟢 A work project whose ALIAS contains a slash.

### [[Personal/Projects/figma-to-site/overview|figma-to-site]]
🟢 A personal project.

### [[Personal/Projects/InBloom Early Learning/overview|InBloom Early Learning]]
🟢 A personal project whose slug contains spaces.

## Backlog

### [[Work/Chalktalk/Projects/Datadog RUM/deferred-thing]]
🟡 A nested work project in the backlog.

## Complete

### [[Work/Chalktalk/Projects/done-thing]] ✅
🟢 Completed, not swept.
"""


def _vault(tmp_path, focus=FOCUS):
    vault = tmp_path / "vault"
    (vault / "Context").mkdir(parents=True)
    (vault / "Context/current-focus.md").write_text(focus)
    return vault


class TestSluggingAgreesWithResolution:
    def test_fixture_actually_covers_the_shapes(self, tmp_path):
        """Premise assertion: a fixture missing these shapes makes every test below vacuous.

        Asserts the SHAPES, never the total — a count would go red when the
        fixture gains a shape, which is exactly when the premise gets stronger.
        """
        swept = dict(session_end._swept_slugs(_vault(tmp_path), "Chalktalk"))
        assert any("/" in s for s in swept), "no nested work entry in fixture"
        assert any(s.count("/") >= 2 for s in swept), "no deeply nested work entry in fixture"
        assert any(" " in s for s in swept), "no space-bearing slug in fixture"
        assert any("-" in s and "/" not in s for s in swept), "no flat work entry in fixture"
        assert any(v == "backlog" for v in swept.values()), "no backlog entry in fixture"

    def test_trailing_space_in_a_heading_does_not_emit_an_unresolvable_slug(self, tmp_path):
        """A slug must round-trip even from a sloppily hand-edited heading.

        Trimming whitespace the resolver does not trim is how the silent no-op
        gets reintroduced, so the extractor must not be more lenient than
        `_find_entry_block`.
        """
        focus = FOCUS.replace(
            "### [[Work/Chalktalk/Projects/flat-project]]",
            "### [[Work/Chalktalk/Projects/spacey ]]",
        )
        vault = _vault(tmp_path, focus)
        lines = (vault / "Context/current-focus.md").read_text().splitlines()
        for slug, _section in session_end._swept_slugs(vault, "Chalktalk"):
            assert session_end._find_entry_block(lines, slug, "Chalktalk") is not None, (
                f"emitted slug {slug!r} resolves to no block"
            )

    def test_every_swept_slug_resolves_to_its_own_block(self, tmp_path):
        """THE invariant. Whatever the extractor emits, the resolver must find."""
        vault = _vault(tmp_path)
        lines = (vault / "Context/current-focus.md").read_text().splitlines()
        unresolved = [
            slug
            for slug, _section in session_end._swept_slugs(vault, "Chalktalk")
            if session_end._find_entry_block(lines, slug, "Chalktalk") is None
        ]
        assert unresolved == [], f"extractor emitted slugs the resolver cannot find: {unresolved}"

    def test_nested_work_entries_keep_their_full_path(self, tmp_path):
        slugs = dict(session_end._swept_slugs(_vault(tmp_path), "Chalktalk"))
        assert "Content/lesson-production/index" in slugs
        assert "Content/curriculum-creation-sop" in slugs
        assert "Content" not in slugs, "siblings collapsed onto their parent directory"

    def test_flat_and_aliased_work_entries_are_unchanged(self, tmp_path):
        slugs = dict(session_end._swept_slugs(_vault(tmp_path), "Chalktalk"))
        assert "flat-project" in slugs
        # The alias contains a slash; the slug must stop at the pipe regardless.
        assert "aliased-project" in slugs

    def test_personal_slug_excludes_the_structural_overview_suffix(self, tmp_path):
        """`/overview` is part of the personal PATH form, not a nesting level."""
        slugs = dict(session_end._swept_slugs(_vault(tmp_path), "Chalktalk"))
        assert "figma-to-site" in slugs
        assert "InBloom Early Learning" in slugs
        assert not any(s.endswith("/overview") for s in slugs)

    def test_sections_are_reported_correctly(self, tmp_path):
        swept = dict(session_end._swept_slugs(_vault(tmp_path), "Chalktalk"))
        assert swept["Content/lesson-production/index"] == "active"
        assert swept["Datadog RUM/deferred-thing"] == "backlog"
        assert "done-thing" not in swept, "Complete section must not be swept"


class TestLegacyKeyMigration:
    """A sidecar written under the collapsed scheme must not reset staleness."""

    def test_nested_slug_inherits_staleness_from_the_collapsed_key(self, tmp_path):
        vault = _vault(tmp_path)
        session_end.save_focus_meta(
            vault, {"projects": {"Content": {"last_worked_on": "2026-08-01"}}}
        )
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk"
        )}
        # Both siblings inherit the parent's date rather than being re-seeded at today.
        for slug in ("Content/lesson-production/index", "Content/curriculum-creation-sop"):
            assert slug in cands, f"{slug} vanished from the sweep"
            assert cands[slug]["days_stale"] == 31

    def test_bare_last_segment_key_is_also_inherited(self, tmp_path):
        """Keys written under an even older scheme used the last path segment."""
        vault = _vault(tmp_path)
        session_end.save_focus_meta(
            vault, {"projects": {"curriculum-creation-sop": {"last_worked_on": "2026-08-01"}}}
        )
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk"
        )}
        assert cands["Content/curriculum-creation-sop"]["days_stale"] == 31

    def test_migration_does_not_touch_slugs_that_already_have_a_key(self, tmp_path):
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {
            "Content": {"last_worked_on": "2026-01-01"},
            "Content/lesson-production/index": {"last_worked_on": "2026-08-20"},
        }})
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk"
        )}
        # Its own key survives, rather than being overwritten by the collapsed
        # parent's much older date...
        stored = session_end.load_focus_meta(vault)["projects"]
        assert stored["Content/lesson-production/index"]["last_worked_on"] == "2026-08-20"
        # ...so at 12 days it is still inside the 14-day window and not yet due,
        # where the parent's 2026-01-01 would have made it wrongly due.
        assert "Content/lesson-production/index" not in cands
        # The sibling with no key of its own still inherits the parent's date.
        assert cands["Content/curriculum-creation-sop"]["days_stale"] == 243

    def test_own_segment_key_outranks_the_shared_parent_key(self, tmp_path):
        """The collapsed root is the LEAST specific candidate, so it goes last.

        Every sibling under a directory collapsed onto the same parent key, so
        that key carries whichever sibling was touched most recently. Preferring
        it would hand a long-stale entry its busiest sibling's date and drop it
        off the sweep — the failure this whole change exists to fix.
        """
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {
            "Content": {"last_worked_on": "2026-08-25"},              # busiest sibling
            "curriculum-creation-sop": {"last_worked_on": "2026-06-17"},  # this entry's own
        }})
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )}
        assert cands["Content/curriculum-creation-sop"]["last_worked_on"] == "2026-06-17"
        assert cands["Content/curriculum-creation-sop"]["days_stale"] == 76
        # The sibling with no key of its own DOES fall back to the parent.
        # Asserted positively against the stored value: "not in cands" would be
        # satisfied equally by a seed at today, so it would stay green with the
        # root fallback deleted.
        stored = session_end.load_focus_meta(vault)["projects"]
        assert stored["Content/lesson-production/index"]["last_worked_on"] == "2026-08-25"

    def test_middle_path_segment_is_a_candidate_too(self, tmp_path):
        """Sidecars hold middle segments, not only the leaf and the root."""
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {
            "lesson-production": {"last_worked_on": "2026-06-17"},
        }})
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )}
        assert cands["Content/lesson-production/index"]["days_stale"] == 76

    def test_a_trailing_index_segment_is_not_treated_as_the_project_name(self, tmp_path):
        """`.../index` names the folder's index file, not the project.

        Structurally the same role `/overview` plays in the personal form, and
        the same conflation this change exists to undo. The directory above it
        carries the identity, so a key literally named `index` must not
        outrank the directory's own key.
        """
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {
            "index": {"last_worked_on": "2026-08-30"},            # generic, wrong
            "lesson-production": {"last_worked_on": "2026-06-17"},  # the real one
        }})
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )}
        assert cands["Content/lesson-production/index"]["last_worked_on"] == "2026-06-17"

    def test_inheritance_never_adopts_a_live_projects_history(self, tmp_path):
        """A key that is itself a live slug is not a legacy key.

        Sharing a path segment with an unrelated flat project must not make a
        brand-new nested project inherit that project's dates — least of all
        its snooze, which would make the new project invisible from birth.
        """
        focus = FOCUS.replace(
            "### [[Work/Chalktalk/Projects/flat-project]]",
            "### [[Work/Chalktalk/Projects/lesson-production]]",
        )
        vault = _vault(tmp_path, focus)
        session_end.save_focus_meta(vault, {"projects": {
            "lesson-production": {"last_worked_on": "2026-08-31", "snooze_until": "2026-12-01"},
        }})
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )}
        stored = session_end.load_focus_meta(vault)["projects"]
        nested = stored["Content/lesson-production/index"]
        assert nested["last_worked_on"] == "2026-09-01", "adopted a live project's date"
        assert "snooze_until" not in nested, "adopted a live project's deferral"
        assert "Content/lesson-production/index" not in cands  # newly seeded, not yet stale

    def test_inheritance_copies_only_last_worked_on(self, tmp_path):
        """A legacy snooze must not ride along and defer the corrected slug."""
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {"Content": {
            "last_worked_on": "2026-08-01", "snooze_until": "2026-12-01",
        }}})
        cands = {c["slug"] for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )}
        assert "Content/curriculum-creation-sop" in cands, "legacy snooze suppressed the candidate"
        stored = session_end.load_focus_meta(vault)["projects"]
        assert "snooze_until" not in stored["Content/curriculum-creation-sop"]

    def test_preflight_dry_run_stays_write_free(self, tmp_path):
        """compute_stale_candidates must not persist when seeding is disabled.

        Preflight calls it with the default seed_missing=False, so a write here
        means every --dry-run mutates the sidecar it was promised not to touch.
        """
        vault = _vault(tmp_path)
        session_end.save_focus_meta(
            vault, {"projects": {"Content": {"last_worked_on": "2026-08-01"}}}
        )
        before = (vault / "Context/.focus-meta.json").read_text()
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk"
        )}
        assert (vault / "Context/.focus-meta.json").read_text() == before, "dry run wrote sidecar"
        # ...and the inheritance still applies in memory, so the gate sees the truth.
        assert cands["Content/curriculum-creation-sop"]["days_stale"] == 31

    def test_snooze_on_a_migrated_slug_survives_a_round_trip(self, tmp_path):
        vault = _vault(tmp_path)
        session_end.save_focus_meta(
            vault, {"projects": {"Content": {"last_worked_on": "2026-08-01"}}}
        )
        session_end.compute_stale_candidates(vault, today=Date(2026, 9, 1), org_name="Chalktalk")
        session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(snooze=["Content/curriculum-creation-sop"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 9, 1),
        )
        entry = session_end.load_focus_meta(vault)["projects"]["Content/curriculum-creation-sop"]
        assert entry["snooze_until"] == "2026-09-15"
        assert entry["last_worked_on"] == "2026-08-01", "inherited staleness was overwritten"


class TestMigrationRunsOnce:
    """Adoption is a migration, not a permanent lookup.

    Left running forever, every orphaned legacy key stays a standing claim on
    any future slug that shares a path segment with it, so a brand-new project
    silently inherits a dead one's date and is born stale.
    """

    def test_marker_is_stamped_on_the_seeding_path(self, tmp_path):
        vault = _vault(tmp_path)
        assert not session_end.load_focus_meta(vault).get(session_end.NESTED_SLUG_MIGRATION)
        session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )
        meta = session_end.load_focus_meta(vault)
        assert meta[session_end.NESTED_SLUG_MIGRATION] == "2026-09-01"

    def test_dry_run_does_not_stamp_the_marker(self, tmp_path):
        vault = _vault(tmp_path)
        session_end.save_focus_meta(
            vault, {"projects": {"Content": {"last_worked_on": "2026-08-01"}}}
        )
        session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk"
        )
        assert not session_end.load_focus_meta(vault).get(session_end.NESTED_SLUG_MIGRATION)

    def test_a_new_project_after_migration_seeds_at_today(self, tmp_path):
        """The orphan left behind by a retired project must not be adoptable."""
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {
            "lesson-production": {"last_worked_on": "2026-06-17"},  # orphan from a dead project
        }})
        # First sweep migrates and stamps.
        session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )
        # A brand-new project appears later, sharing a path segment with the orphan.
        focus = FOCUS.replace(
            "## Backlog",
            "### [[Work/Chalktalk/Projects/Marketing/lesson-production/notes]]\n"
            "🟢 Brand new, unrelated.\n\n## Backlog",
        )
        (vault / "Context/current-focus.md").write_text(focus)
        session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 20), org_name="Chalktalk", seed_missing=True
        )
        stored = session_end.load_focus_meta(vault)["projects"]
        assert stored["Marketing/lesson-production/notes"]["last_worked_on"] == "2026-09-20", (
            "a new project inherited a dead project's date through a shared segment"
        )


    def test_apply_path_migrates_and_stamps_without_stale_check(self, tmp_path):
        """A vault where --stale-check never runs must still migrate exactly once.

        The apply path adopts too, so if only the sweep stamped the marker,
        adoption would run forever here and a later unrelated project sharing a
        path segment would inherit a dead project's date.
        """
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {
            "curriculum-creation-sop": {"last_worked_on": "2026-06-17"},
        }})
        session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(snooze=["Content/curriculum-creation-sop"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 9, 1),
        )
        meta = session_end.load_focus_meta(vault)
        # The migration ran: real staleness kept rather than stamped to today.
        assert meta["projects"]["Content/curriculum-creation-sop"]["last_worked_on"] == "2026-06-17"
        # ...and it is recorded, so it will not run again on this vault.
        assert meta[session_end.NESTED_SLUG_MIGRATION] == "2026-09-01"

    def test_apply_path_migration_covers_slugs_it_was_not_asked_about(self, tmp_path):
        """Stamping after migrating only the touched slugs would strand the rest."""
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {
            "curriculum-creation-sop": {"last_worked_on": "2026-06-17"},
            "Content": {"last_worked_on": "2026-08-25"},
        }})
        session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(snooze=["Content/curriculum-creation-sop"]),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 9, 1),
        )
        projects = session_end.load_focus_meta(vault)["projects"]
        # An entry nobody mentioned in this run was migrated all the same.
        assert projects["Content/lesson-production/index"]["last_worked_on"] == "2026-08-25"

    def test_an_empty_sweep_does_not_burn_the_migration(self, tmp_path):
        """Stamping over a missing current-focus.md would erase real staleness.

        The marker means "the sidecar has been walked under the corrected
        slugs". With nothing to walk that claim is false, and spending the one
        migration there loses it for the entries that appear afterwards.
        """
        vault = tmp_path / "vault"
        (vault / "Context").mkdir(parents=True)
        session_end.save_focus_meta(vault, {"projects": {
            "curriculum-creation-sop": {"last_worked_on": "2026-06-17"},
        }})
        # No current-focus.md yet: the sweep is empty.
        assert session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        ) == []
        assert not session_end.load_focus_meta(vault).get(session_end.NESTED_SLUG_MIGRATION)
        # The file appears later; the migration must still be available.
        (vault / "Context/current-focus.md").write_text(FOCUS)
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )}
        assert cands["Content/curriculum-creation-sop"]["days_stale"] == 76

    def test_index_exclusion_is_consistent_at_every_depth(self, tmp_path):
        """A trailing "index" is a filename at depth two as much as depth three."""
        focus = FOCUS.replace(
            "### [[Work/Chalktalk/Projects/flat-project]]",
            "### [[Work/Chalktalk/Projects/Handbook/index]]",
        )
        vault = _vault(tmp_path, focus)
        session_end.save_focus_meta(vault, {"projects": {
            "index": {"last_worked_on": "2026-08-30"},       # generic, wrong
            "Handbook": {"last_worked_on": "2026-06-17"},    # the real one
        }})
        cands = {c["slug"]: c for c in session_end.compute_stale_candidates(
            vault, today=Date(2026, 9, 1), org_name="Chalktalk", seed_missing=True
        )}
        assert cands["Handbook/index"]["last_worked_on"] == "2026-06-17"


class TestNestedEntryMovesTheRightBlock:
    def test_retiring_a_nested_entry_moves_only_that_entry(self, tmp_path):
        vault = _vault(tmp_path)
        session_end.save_focus_meta(vault, {"projects": {
            "Content/lesson-production/index": {"last_worked_on": "2026-08-01"},
            "Content/curriculum-creation-sop": {"last_worked_on": "2026-08-01"},
        }})
        session_end.process_focus_updates(
            vault=vault,
            updates=session_end.FocusUpdates(
                move_to_retired=["Content/lesson-production/index"],
                snooze=["Content/curriculum-creation-sop"],
            ),
            last_updated_slug="x", org_name="Chalktalk", today=Date(2026, 9, 1),
        )
        text = (vault / "Context/current-focus.md").read_text()
        active = text.split("## Backlog")[0]
        assert "Content/lesson-production/index]]" not in active, "retired entry left in Active"
        assert "Content/curriculum-creation-sop]]" in active, "sibling was moved too"
        assert "Content/lesson-production/index]] 🗄️" in text.split("## Retired Projects")[1]
        # The surviving sibling keeps being tracked.
        assert "Content/curriculum-creation-sop" in session_end.load_focus_meta(vault)["projects"]
