"""
Tests for constraint checking logic.
"""

import pytest
from src.models.domain import MagnitudeBin, SectorDefinition, StarCandidate
from src.astro.visibility import VisibilityResult
from src.core.constraints import (
    filter_candidates_for_bin,
    passes_azimuth_constraint,
    passes_elevation_constraint,
    passes_magnitude_constraint,
)


def make_sector(name="South", az_min=135, az_max=225, el_min=60, el_max=90,
                rising_el_min=None):
    return SectorDefinition(
        name=name, az_min=az_min, az_max=az_max,
        el_min=el_min, el_max=el_max,
        rising_el_min=rising_el_min,
    )


def make_vis(star_index=0, visible=True, alt_min=62, alt_mean=75,
             az_mean=180, in_sector=True):
    return VisibilityResult(
        star_index=star_index,
        visible_full_slot=visible,
        alt_min=alt_min,
        alt_mean=alt_mean,
        az_mean=az_mean,
        in_sector=in_sector,
    )


def make_star(star_id="S1", vmag=1.5):
    return StarCandidate(
        star_id=star_id, star_name=star_id,
        ra_deg=100.0, dec_deg=20.0,
        vmag=vmag, catalog_source="test",
    )


def make_bin(label="NGS_BRIGHT", vmag_min=-99, vmag_max=2, required_count=1):
    return MagnitudeBin(
        label=label, target_type="NGS",
        vmag_min=vmag_min, vmag_max=vmag_max,
        required_count=required_count,
    )


class TestPassesElevation:
    def test_full_slot_visible_passes(self):
        sector = make_sector()
        vis = make_vis(visible=True)
        assert passes_elevation_constraint(vis, sector)

    def test_partial_visibility_fails(self):
        sector = make_sector()
        vis = make_vis(visible=False)
        assert not passes_elevation_constraint(vis, sector)


class TestPassesAzimuth:
    def test_in_sector_passes(self):
        sector = make_sector()
        vis = make_vis(in_sector=True)
        assert passes_azimuth_constraint(vis, sector)

    def test_out_of_sector_fails(self):
        sector = make_sector()
        vis = make_vis(in_sector=False)
        assert not passes_azimuth_constraint(vis, sector)


class TestPassesMagnitude:
    def test_bright_star_in_bright_bin(self):
        star = make_star(vmag=1.0)
        bin_ = make_bin(vmag_min=-99, vmag_max=2)
        assert passes_magnitude_constraint(star, bin_)

    def test_faint_star_not_in_bright_bin(self):
        star = make_star(vmag=5.5)
        bin_ = make_bin(vmag_min=-99, vmag_max=2)
        assert not passes_magnitude_constraint(star, bin_)

    def test_boundary_exclusive_upper(self):
        star = make_star(vmag=2.0)  # exactly at vmag_max=2
        bin_ = make_bin(vmag_min=-99, vmag_max=2)
        # bound is exclusive: vmag < 2 only
        assert not passes_magnitude_constraint(star, bin_)

    def test_boundary_exclusive_lower(self):
        star = make_star(vmag=2.0)  # exactly at vmag_min=2
        bin_ = make_bin(vmag_min=2, vmag_max=4)
        # bound is exclusive: vmag > 2 only
        assert not passes_magnitude_constraint(star, bin_)

    def test_lpc_overlap_region(self):
        """Star with vmag=5.5 should qualify for both NGS_FAINT and LPC."""
        star = make_star(vmag=5.5)
        ngs_faint = make_bin(vmag_min=4, vmag_max=6)
        lpc = make_bin(vmag_min=5, vmag_max=7)
        assert passes_magnitude_constraint(star, ngs_faint)
        assert passes_magnitude_constraint(star, lpc)


class TestFilterCandidates:
    def _make_pairs(self):
        stars = [make_star(f"S{i}", vmag) for i, vmag in enumerate([1.0, 3.0, 5.5, 6.5])]
        viss = [make_vis(i, visible=True, in_sector=True) for i in range(4)]
        return list(zip(stars, viss))

    def test_bright_bin_returns_one(self):
        pairs = self._make_pairs()
        sector = make_sector()
        bin_ = make_bin(vmag_min=-99, vmag_max=2)
        result = filter_candidates_for_bin(pairs, sector, bin_)
        assert len(result) == 1
        assert result[0][0].vmag < 2

    def test_excluded_ids_skip_stars(self):
        pairs = self._make_pairs()
        sector = make_sector()
        bin_ = make_bin(vmag_min=-99, vmag_max=2)
        result = filter_candidates_for_bin(pairs, sector, bin_, excluded_ids={"S0"})
        assert all(p[0].star_id != "S0" for p in result)

    def test_out_of_sector_excluded(self):
        pairs = [(make_star("S1", 1.0), make_vis(0, visible=True, in_sector=False))]
        sector = make_sector()
        bin_ = make_bin(vmag_min=-99, vmag_max=2)
        result = filter_candidates_for_bin(pairs, sector, bin_)
        assert len(result) == 0
