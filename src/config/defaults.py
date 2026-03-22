"""
Default configuration for the CaNaPy April 2026 observing campaign.

OGS / Teide Observatory, Tenerife:
  Lat:  +28° 17' 58"  →  28.2994° N
  Lon:  -16° 30' 35"  →  -16.5097° W
  Alt:   2390 m

Azimuth convention (AltAz, FITS standard):
  North = 0°, East = 90°, South = 180°, West = 270°

Magnitude bins have exclusive bounds: vmag_min < V < vmag_max.
The NGS_BRIGHT lower bound uses -99 to mean "no lower limit" (very bright stars).
Bins 4–6 (NGS_FAINT) and 5–7 (LPC) overlap by design: stars with 5 < V < 6
satisfy both.  By default a star used in one bin is NOT reused in the same
slot+sector (allow_reuse=False); the user may toggle this in the GUI.
"""

from src.models.domain import (
    AppConfig,
    MagnitudeBin,
    ObservatoryConfig,
    ObservingSession,
    SectorDefinition,
)

# ---------------------------------------------------------------------------
# Observatory
# ---------------------------------------------------------------------------

DEFAULT_OBSERVATORY = ObservatoryConfig(
    name="OGS / Teide Observatory",
    latitude_deg=28.2994,
    longitude_deg=-16.5097,
    elevation_m=2390.0,
    timezone="Europe/Madrid",   # UTC+1 after DST in April 2026
)

# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------

DEFAULT_SESSION = ObservingSession(
    start_night="2026-04-02",
    end_night="2026-04-12",
    sunset_local="20:00",   # civil dusk as operating start
    sunrise_local="08:00",  # civil dawn as operating end
    slot_duration_hours=2.0,
)

# ---------------------------------------------------------------------------
# Sectors
# ---------------------------------------------------------------------------
#
# North  (315° – 45°):  wraps through 0° → az_max < az_min → wraps_zero=True
# East   (45° – 135°):  standard range; rising_el_min=55° applies
# South  (135° – 225°): hotspot at EL=70°, AZ=170°
# West   (225° – 315°): standard range

DEFAULT_SECTORS = [
    SectorDefinition(
        name="North",
        az_min=315.0,
        az_max=45.0,
        el_min=60.0,
        el_max=90.0,
        hotspot_el=None,
        hotspot_az=None,
        rising_el_min=None,
        enabled=True,
    ),
    SectorDefinition(
        name="South",
        az_min=135.0,
        az_max=225.0,
        el_min=60.0,
        el_max=90.0,
        hotspot_el=70.0,
        hotspot_az=170.0,
        rising_el_min=None,
        enabled=True,
    ),
    SectorDefinition(
        name="East",
        az_min=45.0,
        az_max=135.0,
        el_min=60.0,
        el_max=90.0,
        hotspot_el=None,
        hotspot_az=None,
        rising_el_min=55.0,   # accept rising stars ≥ 55°
        enabled=True,
    ),
    SectorDefinition(
        name="West",
        az_min=225.0,
        az_max=315.0,
        el_min=60.0,
        el_max=90.0,
        hotspot_el=None,
        hotspot_az=None,
        rising_el_min=None,
        enabled=True,
    ),
]

# ---------------------------------------------------------------------------
# Magnitude bins
# ---------------------------------------------------------------------------
#
# Overlap between NGS_FAINT (4–6) and LPC (5–7) is intentional.
# allow_reuse=False means a star filling one bin is excluded from others
# within the same slot+sector (by default).

DEFAULT_MAGNITUDE_BINS = [
    MagnitudeBin(
        label="NGS_BRIGHT",
        target_type="NGS",
        vmag_min=-99.0,    # no lower limit (includes the very brightest stars)
        vmag_max=2.0,
        required_count=1,
        allow_reuse=False,
    ),
    MagnitudeBin(
        label="NGS_MEDIUM",
        target_type="NGS",
        vmag_min=2.0,
        vmag_max=4.0,
        required_count=1,
        allow_reuse=False,
    ),
    MagnitudeBin(
        label="NGS_FAINT",
        target_type="NGS",
        vmag_min=4.0,
        vmag_max=6.0,
        required_count=1,
        allow_reuse=False,
    ),
    MagnitudeBin(
        label="LPC",
        target_type="LPC",
        vmag_min=5.0,
        vmag_max=7.0,
        required_count=2,
        allow_reuse=False,
    ),
]

# ---------------------------------------------------------------------------
# Full default config
# ---------------------------------------------------------------------------

DEFAULT_APP_CONFIG = AppConfig(
    observatory=DEFAULT_OBSERVATORY,
    session=DEFAULT_SESSION,
    sectors=DEFAULT_SECTORS,
    magnitude_bins=DEFAULT_MAGNITUDE_BINS,
    catalog_source="vizier",
    local_catalog_path="",
    allow_global_reuse=False,
    catalog_vmag_limit=7.5,
    visibility_sample_minutes=10,
    min_dec_filter=-15.0,
    max_dec_filter=70.0,
)
