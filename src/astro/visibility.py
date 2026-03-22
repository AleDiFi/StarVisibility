"""
Visibility checking for StarVisibility.

For each star and time slot:
  1. Compute AltAz at N evenly-spaced sample times.
  2. Determine whether the star stays above el_min for the FULL slot
     (standard rule) or satisfies the "rising" relaxation (East sector).
  3. Record alt_min, alt_mean, az_mean for ranking.

Rising rule (East sector):
  If rising_el_min is defined for the sector AND the star is rising
  (altitude at end of slot > altitude at start), the minimum elevation
  threshold is relaxed from el_min to rising_el_min.
  This allows the scheduler to include stars that start near 55° and
  will improve during the slot, even if they don't reach 60° throughout.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, NamedTuple, Optional

import numpy as np
from astropy.coordinates import EarthLocation

from src.astro.coordinate_transform import compute_altaz_at_times
from src.models.domain import SectorDefinition, StarCandidate


class VisibilityResult(NamedTuple):
    """Result of a visibility check for one star during one time slot."""

    star_index: int          # index into the input list
    visible_full_slot: bool
    alt_min: float
    alt_mean: float
    az_mean: float
    in_sector: bool          # passes azimuth filter at slot midpoint


def check_visibility_batch(
    stars: List[StarCandidate],
    location: EarthLocation,
    utc_times: List[datetime],
    sector: SectorDefinition,
) -> List[VisibilityResult]:
    """
    Check visibility for a batch of stars at the given sample times.

    Parameters
    ----------
    stars : list of StarCandidate
    location : EarthLocation
    utc_times : list of UTC datetime (sample times across the slot)
    sector : SectorDefinition

    Returns
    -------
    list of VisibilityResult, one per star
    """
    from src.astro.coordinate_transform import build_sky_coords

    if not stars:
        return []

    coords = build_sky_coords(stars)
    alts, azs = compute_altaz_at_times(coords, location, utc_times)
    # alts, azs shape: (N_stars, N_times)

    mid = len(utc_times) // 2
    results: List[VisibilityResult] = []

    for i in range(len(stars)):
        star_alts = alts[i]       # shape (N_times,)
        star_azs = azs[i]

        alt_min = float(np.min(star_alts))
        alt_mean = float(np.mean(star_alts))
        az_mean = float(np.mean(star_azs))
        mid_az = float(star_azs[mid])

        in_sector = sector.contains_azimuth(mid_az)

        # --- visibility rule ---
        rising = float(star_alts[-1]) > float(star_alts[0])

        if sector.rising_el_min is not None and rising:
            # East rising relaxation: use the lower threshold
            el_threshold = sector.rising_el_min
        else:
            el_threshold = sector.el_min

        visible_full_slot = bool(np.all(star_alts >= el_threshold))

        results.append(
            VisibilityResult(
                star_index=i,
                visible_full_slot=visible_full_slot,
                alt_min=alt_min,
                alt_mean=alt_mean,
                az_mean=az_mean,
                in_sector=in_sector,
            )
        )

    return results


def prefilter_by_declination(
    stars: List[StarCandidate],
    latitude_deg: float,
    el_min: float,
) -> List[StarCandidate]:
    """
    Remove stars that can NEVER reach *el_min* from the observer's latitude.

    Transit altitude = 90° - |lat - dec|.
    A star can only reach el_min if its transit altitude ≥ el_min.
    This is a coarse filter that eliminates circumpolar-South or very low stars.

    Note: this applies a conservative margin of 2° to avoid edge cases.
    """
    threshold = el_min - 2.0  # conservative
    filtered = []
    for star in stars:
        transit_alt = 90.0 - abs(latitude_deg - star.dec_deg)
        if transit_alt >= threshold:
            filtered.append(star)
    return filtered
