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
        """Premise assertion: a fixture missing these shapes makes every test below vacuous."""
        swept = dict(session_end._swept_slugs(_vault(tmp_path), "Chalktalk"))
        assert any("/" in s for s in swept), "no nested work entry in fixture"
        assert any(" " in s for s in swept), "no space-bearing slug in fixture"
        assert len(swept) == 7, f"expected 7 swept entries, got {sorted(swept)}"

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
