"""
Sector helpers for StarVisibility.

Provides utility functions for sector geometry beyond what the domain model
already covers, and resolves the enabled sector list from the config.
"""

from __future__ import annotations

from typing import List

from src.models.domain import AppConfig, SectorDefinition


def get_enabled_sectors(config: AppConfig) -> List[SectorDefinition]:
    """Return only sectors that are enabled in the configuration."""
    return [s for s in config.sectors if s.enabled]


def validate_sectors(sectors: List[SectorDefinition]) -> List[str]:
    """
    Return a list of warning strings for problematic sector definitions.
    An empty list means everything looks fine.
    """
    warnings: List[str] = []
    names_seen: set = set()

    for sector in sectors:
        if sector.name in names_seen:
            warnings.append(f"Duplicate sector name: {sector.name!r}")
        names_seen.add(sector.name)

        if sector.el_min < 0 or sector.el_min >= 90:
            warnings.append(
                f"Sector {sector.name}: el_min ({sector.el_min}) is out of range [0, 90)."
            )
        if sector.el_max <= sector.el_min:
            warnings.append(
                f"Sector {sector.name}: el_max ({sector.el_max}) ≤ el_min ({sector.el_min})."
            )
        if sector.hotspot_el is not None and (
            sector.hotspot_el < sector.el_min or sector.hotspot_el > sector.el_max
        ):
            warnings.append(
                f"Sector {sector.name}: hotspot elevation {sector.hotspot_el}° "
                f"is outside [{sector.el_min}, {sector.el_max}]."
            )

    return warnings
