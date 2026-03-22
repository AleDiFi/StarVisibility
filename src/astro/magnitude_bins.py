"""
Magnitude bin utilities for StarVisibility.

Handles the overlapping-bin problem:
  NGS_FAINT:  4 < V < 6
  LPC:        5 < V < 7
  Stars with 5 < V < 6 satisfy BOTH bins.

Default behaviour (allow_reuse=False):
  Each star is assigned to at most one bin per slot+sector.
  The assignment is first-come-first-served in the order the bins are listed.
  Once a star fills a slot in bin X it is removed from the candidate pool
  for bin Y in the same slot+sector.

If allow_global_reuse=True (AppConfig level):
  Stars may appear in multiple bins; bins are filled independently.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from src.models.domain import MagnitudeBin, StarCandidate


def assign_stars_to_bins(
    stars: List[StarCandidate],
    bins: List[MagnitudeBin],
    allow_global_reuse: bool = False,
    band: str = "V",
) -> Dict[str, List[StarCandidate]]:
    """
    Partition *stars* into the given magnitude *bins*.

    Parameters
    ----------
    stars : list of StarCandidate
    bins  : ordered list of MagnitudeBin
    allow_global_reuse : if True, a star may appear in multiple bins.
    band  : photometric band to use for the magnitude comparison
            (e.g. 'V', 'J', 'K').  Stars without data in the requested
            band are silently skipped.

    Returns
    -------
    dict mapping bin.label → list of eligible StarCandidates (unsorted)
    """
    result: Dict[str, List[StarCandidate]] = {b.label: [] for b in bins}
    assigned_ids: Set[str] = set()

    for bin_ in bins:
        for star in stars:
            mag = star.mag_for_band(band)
            if mag is None or not bin_.contains(mag):
                continue
            # reuse check
            if not allow_global_reuse and not bin_.allow_reuse:
                if star.star_id in assigned_ids:
                    continue
            result[bin_.label].append(star)

        # Only mark assigned if the bin does not allow reuse
        if not allow_global_reuse and not bin_.allow_reuse:
            # We mark all stars in this bin as tentatively assigned;
            # actual "used" tracking is done at selection time.
            # Here we only track for cross-bin exclusion.
            pass  # assignment tracked at selection time in selector.py

    return result


def stars_for_bin(
    stars: List[StarCandidate],
    bin_: MagnitudeBin,
    band: str = "V",
) -> List[StarCandidate]:
    """Return stars that qualify for a single magnitude bin.

    Stars without data for the requested *band* are excluded.
    """
    result = []
    for s in stars:
        mag = s.mag_for_band(band)
        if mag is not None and bin_.contains(mag):
            result.append(s)
    return result


def total_required(bins: List[MagnitudeBin]) -> int:
    """Return the total number of targets required across all bins."""
    return sum(b.required_count for b in bins)
