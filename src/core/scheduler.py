"""
Scheduler for StarVisibility.

Orchestrates the per-night, per-slot, per-sector selection loop.
Calls into the astro layer for visibility computation and into the
selector for target assignment.

Progress reporting is done via an optional callback so the GUI progress
bar can be updated without the scheduler knowing about Qt.
"""

from __future__ import annotations

import gc
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


def evaluate_carry_over_targets(
    previous_targets: List[SelectedTarget],
    current_slot: TimeSlot,
    sector: SectorDefinition,
    location: EarthLocation,
    sample_minutes: int,
    max_carry_over: int = 20,
) -> List[SelectedTarget]:
    """
    Re-evaluate targets from the previous slot to see if they are still valid
    for the current slot. Returns those that still satisfy constraints.
    
    Parameters
    ----------
    previous_targets : targets selected in the previous slot for this sector
    current_slot : the new slot to evaluate against
    sector : sector definition with constraints
    location : EarthLocation for the observatory
    sample_minutes : sampling interval for visibility computation
    max_carry_over : maximum number of targets to carry over (default: 20)
    
    Returns
    -------
    List of SelectedTarget with carried_over_from_previous_slot=True
    """
    if not previous_targets:
        return []
    
    # Limit the number of previous targets to avoid memory issues
    # Keep the highest-ranked ones
    targets_to_eval = sorted(
        previous_targets, 
        key=lambda t: t.ranking_score, 
        reverse=True
    )[:max_carry_over]
    
    # Extract stars from previous targets
    stars = [t.star for t in targets_to_eval]
    
    # Sample times for the new slot
    utc_times = sample_times_in_slot(
        current_slot.start_utc, current_slot.end_utc, sample_minutes
    )
    
    # Re-compute visibility for the new slot
    vis_results = check_visibility_batch(stars, location, utc_times, sector)
    
    carry_over = []
    for i, vis in enumerate(vis_results):
        if not vis.in_sector:
            # Star no longer satisfies azimuth or elevation constraints
            continue
        
        prev_target = targets_to_eval[i]
        
        # Create a new SelectedTarget for the current slot with updated visibility
        # Keep the same magnitude bin assignment
        notes_parts = ["carried_over"]
        if not vis.visible_full_slot:
            notes_parts.append("partial_visibility")
        
        new_target = SelectedTarget(
            star=prev_target.star,
            slot=current_slot,
            sector=sector,
            mag_bin=prev_target.mag_bin,
            alt_min_deg=vis.alt_min,
            alt_mean_deg=vis.alt_mean,
            az_mean_deg=vis.az_mean,
            visible_full_slot=vis.visible_full_slot,
            repeated_from_previous_slot=False,  # This is a carry-over, not a repeat
            carried_over_from_previous_slot=True,
            hotspot_distance_deg=sector.distance_to_hotspot(vis.az_mean, vis.alt_mean),
            ranking_score=prev_target.ranking_score,  # Keep previous ranking
            notes="; ".join(notes_parts),
        )
        carry_over.append(new_target)
    
    log.debug(
        "Carry-over evaluation: %d previous → %d still valid for slot %s sector %s",
        len(previous_targets), len(carry_over), 
        current_slot.display_label, sector.name
    )
    
    return carry_over


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

    # Track which star IDs were selected per sector in the previous slot (for ranking penalty)
    prev_selected_ids: Dict[str, Set[str]] = {s.name: set() for s in enabled_sectors}
    # Track full SelectedTarget objects from previous slot (for carry-over evaluation)
    prev_selected_targets: Dict[str, List[SelectedTarget]] = {s.name: [] for s in enabled_sectors}

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
                previously_selected_ids=prev_selected_ids[sector.name],
                band=band,
            )

            # Evaluate carry-over: re-check stars from previous slot
            carry_over = evaluate_carry_over_targets(
                previous_targets=prev_selected_targets[sector.name],
                current_slot=slot,
                sector=sector,
                location=location,
                sample_minutes=sample_minutes,
            )
            
            # Add carry-over targets to the selection
            # (these are in addition to the required targets per bin)
            selected.extend(carry_over)
            
            if carry_over:
                log.info(
                    "Added %d carry-over targets for %s | %s",
                    len(carry_over), slot.display_label, sector.name
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
        # Note: we only carry forward newly selected targets, not those that were
        # already carry-overs, to avoid indefinite propagation
        for sector in enabled_sectors:
            this_slot_targets = [
                t for t in result.selected_targets
                if t.slot is slot and t.sector is sector 
                and not t.carried_over_from_previous_slot
            ]
            this_slot_ids = {t.star.star_id for t in this_slot_targets}
            prev_selected_ids[sector.name] = this_slot_ids
            prev_selected_targets[sector.name] = this_slot_targets
        
        # Force garbage collection after each slot to free memory
        gc.collect()

    log.info(
        "Scheduling complete: %d targets selected, %d/%d slot-sectors fully covered.",
        len(result.selected_targets),
        sum(1 for c in result.coverage if c.fully_covered),
        len(result.coverage),
    )
    return result
