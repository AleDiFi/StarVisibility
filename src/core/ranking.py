"""
Target ranking for StarVisibility.

Implements a configurable, extensible scoring strategy.

Default ranking order (higher score = better candidate):
  1. Visibility bonus: full-slot visibility → +1000 pts
  2. Mean elevation: +1 pt per degree (range 55–90° → up to 90 pts)
  3. Distance from sector azimuth centre: -0.3 pt per degree off-centre
  4. South hotspot bonus: exponential decay, max +100 pts when on hotspot
  5. Repeat penalty: -80 pts if this star was selected in the previous slot

All weights are centralised in config/settings.py and can be adjusted.
"""

from __future__ import annotations

import math
from typing import List, Optional, Set

from src.astro.visibility import VisibilityResult
from src.config.settings import (
    RANK_ALT_WEIGHT,
    RANK_AZ_CENTER_PENALTY,
    RANK_FULL_VISIBILITY_BONUS,
    RANK_HOTSPOT_BONUS_MAX,
    RANK_HOTSPOT_SCALE,
    RANK_REPEAT_PENALTY,
)
from src.models.domain import SectorDefinition, StarCandidate


def score_candidate(
    star: StarCandidate,
    vis: VisibilityResult,
    sector: SectorDefinition,
    previously_selected_ids: Optional[Set[str]] = None,
) -> float:
    """
    Compute a ranking score for a candidate (star, visibility) pair.

    Parameters
    ----------
    star : StarCandidate
    vis  : VisibilityResult for this star in the current slot
    sector : SectorDefinition
    previously_selected_ids : set of star IDs selected in the previous slot
                              (used to apply the repeat penalty)

    Returns
    -------
    float score (higher = better)
    """
    score = 0.0

    # 1. Full visibility
    if vis.visible_full_slot:
        score += RANK_FULL_VISIBILITY_BONUS

    # 2. Mean elevation
    score += vis.alt_mean * RANK_ALT_WEIGHT

    # 3. Azimuth proximity to sector centre
    az_dist = _az_angular_distance(vis.az_mean, sector.az_center)
    score -= az_dist * RANK_AZ_CENTER_PENALTY

    # 4. Hotspot bonus (South sector)
    hotspot_dist = sector.distance_to_hotspot(vis.az_mean, vis.alt_mean)
    if hotspot_dist is not None:
        bonus = RANK_HOTSPOT_BONUS_MAX * math.exp(-hotspot_dist / RANK_HOTSPOT_SCALE)
        score += bonus

    # 5. Repeat penalty
    if previously_selected_ids and star.star_id in previously_selected_ids:
        score -= RANK_REPEAT_PENALTY

    return score


def rank_candidates(
    pairs: list,                   # List[Tuple[StarCandidate, VisibilityResult]]
    sector: SectorDefinition,
    previously_selected_ids: Optional[Set[str]] = None,
) -> list:
    """
    Return *pairs* sorted by descending score (best first).

    Parameters
    ----------
    pairs : list of (StarCandidate, VisibilityResult)
    sector : SectorDefinition
    previously_selected_ids : optional set of star IDs from previous slot

    Returns
    -------
    sorted list of (StarCandidate, VisibilityResult, score)
    """
    scored = []
    for star, vis in pairs:
        s = score_candidate(star, vis, sector, previously_selected_ids)
        scored.append((star, vis, s))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _az_angular_distance(az1: float, az2: float) -> float:
    """
    Shortest angular distance between two azimuth values [0, 360).
    Always in [0, 180].
    """
    diff = abs(az1 - az2) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff
