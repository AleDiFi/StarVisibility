"""
Scheduler for StarVisibility.

Orchestrates the per-night, per-slot, per-sector selection loop.
Calls into the astro layer for visibility computation and into the
selector for target assignment.

Progress reporting is done via an optional callback so the GUI progress
bar can be updated without the scheduler knowing about Qt.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Set, Tuple

from astropy.coordinates import EarthLocation

from src.astro.visibility import check_visibility_batch, prefilter_by_declination
from src.core.selector import select_targets_for_slot_sector
from src.models.domain import (
    AppConfig,
    PlanningResult,
    SectorDefinition,
    SelectedTarget,
    SlotSectorCoverage,
    StarCandidate,
    TimeSlot,
)
from src.utils.datetime_utils import sample_times_in_slot
from src.utils.logging_utils import get_logger

log = get_logger("scheduler")

ProgressCallback = Callable[[int, int, str], None]  # (current, total, message)


def run_scheduler(
    config: AppConfig,
    all_stars: List[StarCandidate],
    slots: List[TimeSlot],
    location: EarthLocation,
    progress_callback: Optional[ProgressCallback] = None,
) -> PlanningResult:
    """
    Main scheduling loop.

    For each slot and each enabled sector:
      1. Pre-filter stars by declination (coarse geometric filter).
      2. Sample alt/az at regular intervals across the slot.
      3. Check azimuth and elevation constraints (visibility.py).
      4. Select targets per magnitude bin (selector.py).
      5. Track cross-slot repeat state for penalty calculation.

    Parameters
    ----------
    config : AppConfig
    all_stars : full catalog (pre-loaded StarCandidate list)
    slots : sorted list of TimeSlot objects
    location : EarthLocation for the observatory
    progress_callback : optional function(current, total, message)

    Returns
    -------
    PlanningResult
    """
    result = PlanningResult(slots=slots)
    enabled_sectors = [s for s in config.sectors if s.enabled]
    sample_minutes = config.visibility_sample_minutes
    band = config.catalog_band          # photometric band for magnitude filtering

    # Track which star IDs were selected per sector in the previous slot
    prev_selected: Dict[str, Set[str]] = {s.name: set() for s in enabled_sectors}

    total_steps = len(slots) * len(enabled_sectors)
    step = 0

    # Coarse pre-filter by declination: remove stars that can never
    # reach any sector's el_min from the observer's latitude
    global_el_min = min(s.el_min for s in enabled_sectors) if enabled_sectors else 55.0
    lat = config.observatory.latitude_deg
    pre_filtered = prefilter_by_declination(all_stars, lat, global_el_min)
    log.info(
        "Pre-filter by declination: %d → %d stars",
        len(all_stars), len(pre_filtered)
    )

    for slot in slots:
        utc_times = sample_times_in_slot(
            slot.start_utc, slot.end_utc, sample_minutes
        )

        for sector in enabled_sectors:
            step += 1
            msg = (
                f"Night {slot.night_label} | {slot.display_label} | {sector.name}"
            )
            log.debug("Processing: %s", msg)
            if progress_callback:
                progress_callback(step, total_steps, msg)

            # Sector-specific magnitude-based pre-filter (coarse, uses vmag).
            # Stars without the target band mag are kept here and excluded
            # later in filter_candidates_for_bin (which checks the exact band).
            vmag_max = max(b.vmag_max for b in config.magnitude_bins)
            sector_stars = [
                s for s in pre_filtered if s.vmag < vmag_max
            ]

            # Compute AltAz for all remaining stars
            vis_results = check_visibility_batch(
                sector_stars, location, utc_times, sector
            )

            # Pair each star with its visibility result
            pairs = [
                (sector_stars[vr.star_index], vr)
                for vr in vis_results
                if vr.in_sector   # pre-filter by azimuth early
            ]

            # Select targets per bin
            selected, coverage = select_targets_for_slot_sector(
                slot=slot,
                sector=sector,
                magnitude_bins=config.magnitude_bins,
                stars_with_results=pairs,
                allow_global_reuse=config.allow_global_reuse,
                previously_selected_ids=prev_selected[sector.name],
                band=band,
            )

            result.selected_targets.extend(selected)
            result.coverage.append(coverage)

            if not coverage.fully_covered:
                result.warnings.append(
                    f"⚠  Incomplete coverage: {msg} | "
                    f"missing bins: {', '.join(coverage.missing_bins)}"
                )
                log.warning(
                    "Incomplete coverage at %s sector=%s: %s",
                    slot.display_label, sector.name, coverage.missing_bins
                )

        # Update previous-slot state for the next slot
        for sector in enabled_sectors:
            this_slot_ids = {
                t.star.star_id
                for t in result.selected_targets
                if t.slot is slot and t.sector is sector
            }
            prev_selected[sector.name] = this_slot_ids

    log.info(
        "Scheduling complete: %d targets selected, %d/%d slot-sectors fully covered.",
        len(result.selected_targets),
        sum(1 for c in result.coverage if c.fully_covered),
        len(result.coverage),
    )
    return result
