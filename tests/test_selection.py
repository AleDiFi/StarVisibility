"""
Tests for the target selector and ranking logic.
"""

import pytest
from datetime import datetime, timezone

from src.models.domain import (
    MagnitudeBin,
    SectorDefinition,
    SelectedTarget,
    SlotSectorCoverage,
    StarCandidate,
    TimeSlot,
)
from src.astro.visibility import VisibilityResult
from src.core.ranking import rank_candidates, score_candidate, _az_angular_distance
from src.core.selector import select_targets_for_slot_sector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc


def make_slot(night="2026-04-02", idx=0):
    start = datetime(2026, 4, 2, 19, 0, tzinfo=UTC)
    end = datetime(2026, 4, 2, 21, 0, tzinfo=UTC)
    return TimeSlot(
        night_label=night, slot_index=idx,
        start_utc=start, end_utc=end,
        start_local=start, end_local=end,
    )


def make_sector(name="South", az_min=135, az_max=225, el_min=60, el_max=90,
                hotspot_el=None, hotspot_az=None, rising_el_min=None):
    return SectorDefinition(
        name=name, az_min=az_min, az_max=az_max,
        el_min=el_min, el_max=el_max,
        hotspot_el=hotspot_el, hotspot_az=hotspot_az,
        rising_el_min=rising_el_min,
    )


def make_star(star_id="S1", vmag=1.5, ra=100.0, dec=20.0):
    return StarCandidate(
        star_id=star_id, star_name=star_id,
        ra_deg=ra, dec_deg=dec,
        vmag=vmag, catalog_source="test",
    )


def make_vis(star_index=0, visible=True, alt_min=65, alt_mean=75,
             az_mean=180, in_sector=True):
    return VisibilityResult(
        star_index=star_index,
        visible_full_slot=visible,
        alt_min=alt_min,
        alt_mean=alt_mean,
        az_mean=az_mean,
        in_sector=in_sector,
    )


def make_bin(label="NGS_BRIGHT", vmag_min=-99, vmag_max=2, required_count=1):
    return MagnitudeBin(
        label=label, target_type="NGS",
        vmag_min=vmag_min, vmag_max=vmag_max,
        required_count=required_count,
    )


# ---------------------------------------------------------------------------
# Tests: ranking utilities
# ---------------------------------------------------------------------------

class TestAzAngularDistance:
    def test_same_azimuth(self):
        assert _az_angular_distance(90.0, 90.0) == pytest.approx(0.0)

    def test_opposite_azimuth(self):
        assert _az_angular_distance(0.0, 180.0) == pytest.approx(180.0)

    def test_wraparound(self):
        # Distance from 350° to 10° is 20°, not 340°
        assert _az_angular_distance(350.0, 10.0) == pytest.approx(20.0)


class TestScoreCandidate:
    def test_full_visibility_adds_bonus(self):
        sector = make_sector()
        star = make_star()
        vis_full = make_vis(visible=True, alt_mean=75)
        vis_partial = make_vis(visible=False, alt_mean=75)
        s_full = score_candidate(star, vis_full, sector)
        s_partial = score_candidate(star, vis_partial, sector)
        # Full visibility should score much higher
        assert s_full > s_partial + 900

    def test_higher_elevation_scores_higher(self):
        sector = make_sector()
        star = make_star()
        vis_low = make_vis(alt_mean=61)
        vis_high = make_vis(alt_mean=85)
        assert score_candidate(star, vis_high, sector) > score_candidate(star, vis_low, sector)

    def test_hotspot_bonus_applied(self):
        sector_with = make_sector(hotspot_el=70, hotspot_az=180)
        sector_without = make_sector()
        star = make_star()
        vis = make_vis(alt_mean=70, az_mean=180)
        s_with = score_candidate(star, vis, sector_with)
        s_without = score_candidate(star, vis, sector_without)
        assert s_with > s_without

    def test_repeat_penalty_applied(self):
        sector = make_sector()
        star = make_star(star_id="S1")
        vis = make_vis()
        s_fresh = score_candidate(star, vis, sector, previously_selected_ids=set())
        s_repeat = score_candidate(star, vis, sector, previously_selected_ids={"S1"})
        assert s_fresh > s_repeat


class TestRankCandidates:
    def test_sorted_best_first(self):
        sector = make_sector()
        pairs = [
            (make_star("S1", 1.0), make_vis(0, visible=True, alt_mean=80)),
            (make_star("S2", 1.5), make_vis(1, visible=False, alt_mean=65)),
        ]
        ranked = rank_candidates(pairs, sector)
        assert ranked[0][0].star_id == "S1"
        assert ranked[1][0].star_id == "S2"


# ---------------------------------------------------------------------------
# Tests: selector
# ---------------------------------------------------------------------------

class TestSelectTargetsForSlotSector:
    def _make_scenario(self, n_bright=2, n_medium=2):
        """Create a scenario with bright and medium stars."""
        stars = []
        pairs = []

        for i in range(n_bright):
            s = make_star(f"BRIGHT_{i}", vmag=1.5)
            v = make_vis(i, visible=True, alt_mean=75, az_mean=180, in_sector=True)
            stars.append(s)
            pairs.append((s, v))

        for i in range(n_medium):
            s = make_star(f"MED_{i}", vmag=3.0)
            v = make_vis(n_bright + i, visible=True, alt_mean=70, az_mean=180, in_sector=True)
            stars.append(s)
            pairs.append((s, v))

        return pairs

    def test_selects_required_count(self):
        sector = make_sector()
        slot = make_slot()
        pairs = self._make_scenario(n_bright=3, n_medium=3)
        bins = [
            make_bin("NGS_BRIGHT", vmag_min=-99, vmag_max=2, required_count=1),
            make_bin("NGS_MEDIUM", vmag_min=2, vmag_max=4, required_count=1),
        ]
        targets, coverage = select_targets_for_slot_sector(
            slot, sector, bins, pairs, allow_global_reuse=False,
            previously_selected_ids=None,
        )
        assert len(targets) == 2
        assert coverage.targets_found == 2
        assert coverage.fully_covered

    def test_coverage_reports_missing_when_no_candidates(self):
        sector = make_sector()
        slot = make_slot()
        pairs = []  # no stars at all
        bins = [make_bin("NGS_BRIGHT", vmag_min=-99, vmag_max=2, required_count=1)]
        targets, coverage = select_targets_for_slot_sector(
            slot, sector, bins, pairs, allow_global_reuse=False,
            previously_selected_ids=None,
        )
        assert len(targets) == 0
        assert not coverage.fully_covered
        assert len(coverage.missing_bins) == 1

    def test_no_reuse_within_slot_sector(self):
        """A star in the overlap (5 < V < 6) should not fill both NGS_FAINT and LPC
        when allow_global_reuse=False."""
        sector = make_sector()
        slot = make_slot()
        # Only one star, vmag=5.5 → qualifies for both NGS_FAINT and LPC
        star = make_star("OVL", vmag=5.5)
        vis = make_vis(0, visible=True, in_sector=True)
        pairs = [(star, vis)]
        bins = [
            MagnitudeBin("NGS_FAINT", "NGS", 4.0, 6.0, required_count=1),
            MagnitudeBin("LPC", "LPC", 5.0, 7.0, required_count=1),
        ]
        targets, coverage = select_targets_for_slot_sector(
            slot, sector, bins, pairs, allow_global_reuse=False,
            previously_selected_ids=None,
        )
        star_ids_used = [t.star.star_id for t in targets]
        # The star should appear at most once
        assert star_ids_used.count("OVL") == 1
        # LPC bin will be missing
        assert not coverage.fully_covered

    def test_repeated_flag_set(self):
        sector = make_sector()
        slot = make_slot()
        star = make_star("S1", vmag=1.0)
        vis = make_vis(0, visible=True, in_sector=True)
        pairs = [(star, vis)]
        bins = [make_bin("NGS_BRIGHT", vmag_min=-99, vmag_max=2, required_count=1)]
        targets, _ = select_targets_for_slot_sector(
            slot, sector, bins, pairs, allow_global_reuse=False,
            previously_selected_ids={"S1"},  # was selected last slot
        )
        assert targets[0].repeated_from_previous_slot is True
