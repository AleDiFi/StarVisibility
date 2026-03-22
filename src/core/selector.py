"""
Target selector for StarVisibility.

For each slot+sector combination, selects the required number of stars
per magnitude bin using the ranking strategy from core/ranking.py.

Reuse policy:
  - Within a slot+sector: by default (allow_global_reuse=False) a star
    once assigned to a bin is removed from the pool for subsequent bins.
    Stars with an overlapping vmag range (e.g., 5 < V < 6 satisfying both
    NGS_FAINT and LPC) will therefore appear in at most one bin.
  - A star appearing in the previous slot for the same sector is penalised
    in ranking but NOT excluded (it may be the only valid option).
    The repeated_from_previous_slot flag is set on the SelectedTarget.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from src.astro.visibility import VisibilityResult
from src.core.constraints import filter_candidates_for_bin
from src.core.ranking import rank_candidates
from src.models.domain import (
    AppConfig,
    MagnitudeBin,
    SectorDefinition,
    SelectedTarget,
    SlotSectorCoverage,
    StarCandidate,
    TimeSlot,
)


def select_targets_for_slot_sector(
    slot: TimeSlot,
    sector: SectorDefinition,
    magnitude_bins: List[MagnitudeBin],
    stars_with_results: List[Tuple[StarCandidate, VisibilityResult]],
    allow_global_reuse: bool,
    previously_selected_ids: Optional[Set[str]],
    band: str = "V",
) -> Tuple[List[SelectedTarget], SlotSectorCoverage]:
    """
    Select targets for one slot / sector combination.

    Parameters
    ----------
    slot : TimeSlot
    sector : SectorDefinition
    magnitude_bins : ordered list of MagnitudeBin
    stars_with_results : (StarCandidate, VisibilityResult) pairs
                         already filtered to pass azimuth constraint
    allow_global_reuse : if True, a star can fill multiple bins
    previously_selected_ids : star IDs selected in the previous slot
                              for this same sector (for repeat detection)

    Returns
    -------
    (selected_targets, coverage_summary)
    """
    selected: List[SelectedTarget] = []
    used_in_slot_sector: Set[str] = set()   # tracks intra-slot reuse
    missing_bins: List[str] = []

    for bin_ in magnitude_bins:
        excluded = set() if allow_global_reuse else used_in_slot_sector
        candidates = filter_candidates_for_bin(
            stars_with_results, sector, bin_, excluded_ids=excluded, band=band
        )

        ranked = rank_candidates(candidates, sector, previously_selected_ids)

        n_taken = 0
        for star, vis, score in ranked:
            if n_taken >= bin_.required_count:
                break

            hotspot_dist = sector.distance_to_hotspot(vis.az_mean, vis.alt_mean)
            repeated = (
                previously_selected_ids is not None
                and star.star_id in previously_selected_ids
            )

            notes_parts = []
            if repeated:
                notes_parts.append("repeated_from_prev_slot")
            if not vis.visible_full_slot:
                notes_parts.append("partial_visibility")

            target = SelectedTarget(
                star=star,
                slot=slot,
                sector=sector,
                mag_bin=bin_,
                alt_min_deg=vis.alt_min,
                alt_mean_deg=vis.alt_mean,
                az_mean_deg=vis.az_mean,
                visible_full_slot=vis.visible_full_slot,
                repeated_from_previous_slot=repeated,
                hotspot_distance_deg=hotspot_dist,
                ranking_score=score,
                notes="; ".join(notes_parts),
            )
            selected.append(target)
            if not allow_global_reuse:
                used_in_slot_sector.add(star.star_id)
            n_taken += 1

        if n_taken < bin_.required_count:
            missing_bins.append(
                f"{bin_.label} ({n_taken}/{bin_.required_count})"
            )

    total_required = sum(b.required_count for b in magnitude_bins)
    coverage = SlotSectorCoverage(
        night_label=slot.night_label,
        slot_label=slot.label,
        slot_display=slot.display_label,
        sector_name=sector.name,
        fully_covered=len(missing_bins) == 0,
        targets_found=len(selected),
        targets_required=total_required,
        missing_bins=missing_bins,
    )

    return selected, coverage
