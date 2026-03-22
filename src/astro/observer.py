"""
Observatory / observer setup using astropy EarthLocation.
"""

from __future__ import annotations

import astropy.units as u
from astropy.coordinates import EarthLocation

from src.models.domain import ObservatoryConfig


def build_earth_location(config: ObservatoryConfig) -> EarthLocation:
    """
    Construct an astropy EarthLocation from an ObservatoryConfig.

    Parameters
    ----------
    config : ObservatoryConfig
        Site parameters (lat, lon in degrees, elevation in metres).

    Returns
    -------
    EarthLocation
        Geodetic location suitable for AltAz frame construction.
    """
    return EarthLocation(
        lat=config.latitude_deg * u.deg,
        lon=config.longitude_deg * u.deg,
        height=config.elevation_m * u.m,
    )
