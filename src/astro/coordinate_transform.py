"""
Coordinate transformation utilities for StarVisibility.

Converts ICRS (RA/Dec J2000) star positions to the AltAz frame
at the observer's location and a given UTC time (or array of times).

Azimuth convention (astropy AltAz): North=0°, East=90°, South=180°, West=270°.
This matches the geographic/compass convention and is consistent with
the sector definitions in domain.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

import numpy as np
import astropy.units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time

from src.models.domain import StarCandidate


def _to_astropy_time(dt: datetime) -> Time:
    """Convert a datetime (must be UTC-aware) to astropy Time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return Time(dt, scale="utc")


def build_sky_coords(stars: List[StarCandidate]) -> SkyCoord:
    """
    Pack a list of StarCandidate objects into a single SkyCoord array
    for vectorised coordinate transformation.
    """
    ra = np.array([s.ra_deg for s in stars], dtype=np.float64)
    dec = np.array([s.dec_deg for s in stars], dtype=np.float64)
    return SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")


def compute_altaz_at_times(
    coords: SkyCoord,
    location: EarthLocation,
    utc_times: List[datetime],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute altitude and azimuth for *all* stars at *all* sample times.

    Parameters
    ----------
    coords : SkyCoord
        Array of N_stars positions (ICRS).
    location : EarthLocation
        Observer location.
    utc_times : list[datetime]
        List of N_times UTC datetimes.

    Returns
    -------
    alts : np.ndarray, shape (N_stars, N_times)
        Altitude in degrees.
    azs  : np.ndarray, shape (N_stars, N_times)
        Azimuth in degrees [0, 360).
    """
    n_stars = len(coords)
    n_times = len(utc_times)

    if n_stars == 0:
        return np.empty((0, n_times)), np.empty((0, n_times))

    # Build a flat time array (each time repeated n_stars times)
    astropy_times = Time([_to_astropy_time(t) for t in utc_times])

    # Tile stars and times to match each other shape (N_stars * N_times,)
    ra_tile = np.tile(coords.ra.deg, n_times)
    dec_tile = np.tile(coords.dec.deg, n_times)
    t_repeat = np.repeat(astropy_times, n_stars)

    flat_coords = SkyCoord(ra=ra_tile * u.deg, dec=dec_tile * u.deg, frame="icrs")
    frame = AltAz(obstime=t_repeat, location=location)
    altaz = flat_coords.transform_to(frame)

    alts = altaz.alt.deg.reshape(n_times, n_stars).T   # → (N_stars, N_times)
    azs = altaz.az.deg.reshape(n_times, n_stars).T

    return alts, azs


def angular_separation_deg(az1: float, el1: float, az2: float, el2: float) -> float:
    """
    Spherical angular separation between two alt/az points.
    Elevations are used as latitudes, azimuths as longitudes.
    """
    c1 = SkyCoord(az=az1 * u.deg, alt=el1 * u.deg, frame="altaz")
    c2 = SkyCoord(az=az2 * u.deg, alt=el2 * u.deg, frame="altaz")
    return float(c1.separation(c2).deg)
