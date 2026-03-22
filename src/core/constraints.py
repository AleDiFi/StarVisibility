"""
Constraint checking for StarVisibility.

High-level constraint predicates that combine altitude, azimuth, and
magnitude range checks into a single acceptance test.

Note: The lowest-level per-sample visibility is computed in astro/visibility.py.
This module provides higher-level guard functions used by the selector.
"""

from __future__ import annotations

from typing import List, Optional

from src.models.domain import MagnitudeBin, SectorDefinition, StarCandidate
from src.astro.visibility import VisibilityResult


def passes_elevation_constraint(
    result: VisibilityResult,
    sector: SectorDefinition,
) -> bool:
    """
    Return True if the star satisfies the elevation constraint for the sector.

    - For standard sectors: must be visible for the FULL slot.
    - For sectors with rising_el_min: visibility_check already handled
      the rising relaxation; visible_full_slot reflects the relaxed check.
    """
    return result.visible_full_slot


def passes_azimuth_constraint(
    result: VisibilityResult,
    sector: SectorDefinition,
) -> bool:
    """Return True if the star's mean azimuth falls within the sector."""
    return result.in_sector


def passes_magnitude_constraint(
    star: StarCandidate,
    bin_: MagnitudeBin,
    band: str = "V",
) -> bool:
    """Return True if the star's magnitude in *band* falls within the bin.

    Returns False when the star has no data for *band*.
    """
    mag = star.mag_for_band(band)
    if mag is None:
        return False
    return bin_.contains(mag)


def passes_all_constraints(
    result: VisibilityResult,
    star: StarCandidate,
    sector: SectorDefinition,
    bin_: MagnitudeBin,
    band: str = "V",
) -> bool:
    """
    Combined constraint check: elevation + azimuth + magnitude.
    """
    return (
        passes_azimuth_constraint(result, sector)
        and passes_elevation_constraint(result, sector)
        and passes_magnitude_constraint(star, bin_, band)
    )


def filter_candidates_for_bin(
    stars_with_results: List[tuple[StarCandidate, VisibilityResult]],
    sector: SectorDefinition,
    bin_: MagnitudeBin,
    excluded_ids: Optional[set] = None,
    band: str = "V",
) -> List[tuple[StarCandidate, VisibilityResult]]:
    """
    Filter (star, visibility_result) pairs that satisfy all constraints
    for the given sector and magnitude bin.

    Parameters
    ----------
    stars_with_results : pairs of (StarCandidate, VisibilityResult)
    sector : SectorDefinition
    bin_   : MagnitudeBin
    excluded_ids : star IDs already used in this slot+sector (to avoid reuse)
    band   : photometric band for the magnitude constraint.

    Returns
    -------
    list of (StarCandidate, VisibilityResult) passing all constraints
    """
    excluded = excluded_ids or set()
    passed = []
    for star, vis in stars_with_results:
        if star.star_id in excluded:
            continue
        if passes_all_constraints(vis, star, sector, bin_, band):
            passed.append((star, vis))
    return passed
