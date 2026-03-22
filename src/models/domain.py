"""
Domain models for StarVisibility planner.

All data structures are plain dataclasses for lightweight, typed storage.
No external dependencies beyond stdlib.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Observatory
# ---------------------------------------------------------------------------


@dataclass
class ObservatoryConfig:
    """Configuration for the observing site."""

    name: str
    latitude_deg: float       # positive = North
    longitude_deg: float      # positive = East, negative = West
    elevation_m: float        # metres above sea level
    timezone: str             # IANA tz string, e.g. "Europe/Madrid"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "elevation_m": self.elevation_m,
            "timezone": self.timezone,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ObservatoryConfig":
        return cls(
            name=d["name"],
            latitude_deg=float(d["latitude_deg"]),
            longitude_deg=float(d["longitude_deg"]),
            elevation_m=float(d["elevation_m"]),
            timezone=d["timezone"],
        )


# ---------------------------------------------------------------------------
# Observing session
# ---------------------------------------------------------------------------


@dataclass
class ObservingSession:
    """Defines the overall observing campaign dates and nightly window.

    Sliding-window slots
    --------------------
    ``slot_duration_hours`` sets the width of each observing window.
    ``slot_step_hours`` sets how often a new window starts.  When
    ``slot_step_hours < slot_duration_hours`` the windows overlap (sliding
    window): e.g. duration=2h, step=1h gives windows 20-22, 21-23, 22-00 …
    """

    start_night: str        # ISO date of first night "YYYY-MM-DD"
    end_night: str          # ISO date of last night "YYYY-MM-DD"
    sunset_local: str       # "HH:MM"  local time
    sunrise_local: str      # "HH:MM"  local time (next calendar day)
    slot_duration_hours: float = 2.0   # width of each slot [hours]
    slot_step_hours: float = 1.0       # advance between consecutive slot starts [hours]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_night": self.start_night,
            "end_night": self.end_night,
            "sunset_local": self.sunset_local,
            "sunrise_local": self.sunrise_local,
            "slot_duration_hours": self.slot_duration_hours,
            "slot_step_hours": self.slot_step_hours,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ObservingSession":
        return cls(
            start_night=d["start_night"],
            end_night=d["end_night"],
            sunset_local=d["sunset_local"],
            sunrise_local=d["sunrise_local"],
            slot_duration_hours=float(d.get("slot_duration_hours", 2.0)),
            slot_step_hours=float(d.get("slot_step_hours", 1.0)),
        )


# ---------------------------------------------------------------------------
# Time slot
# ---------------------------------------------------------------------------


@dataclass
class TimeSlot:
    """A single observing time block within a night."""

    night_label: str        # "YYYY-MM-DD"  (date of sunset)
    slot_index: int         # 0-based index within the night
    start_utc: datetime
    end_utc: datetime
    start_local: datetime
    end_local: datetime

    @property
    def label(self) -> str:
        return f"slot{self.slot_index:02d}"

    @property
    def display_label(self) -> str:
        return (
            f"{self.night_label}  "
            f"{self.start_local.strftime('%H:%M')}–{self.end_local.strftime('%H:%M')} LT"
        )


# ---------------------------------------------------------------------------
# Sector
# ---------------------------------------------------------------------------


@dataclass
class SectorDefinition:
    """
    Defines an azimuth/elevation sector of the sky.

    Azimuth convention: North = 0°, East = 90°, South = 180°, West = 270°.
    The North sector crosses 0° (az_max < az_min when wrapping).
    """

    name: str           # "North" | "South" | "East" | "West"
    az_min: float       # degrees [0, 360)
    az_max: float       # degrees [0, 360)  may be < az_min for North
    el_min: float       # minimum elevation
    el_max: float       # maximum elevation
    hotspot_el: Optional[float] = None   # preferred elevation target
    hotspot_az: Optional[float] = None   # preferred azimuth target
    rising_el_min: Optional[float] = None  # East: accept if el > this when rising
    enabled: bool = True

    # --- geometry helpers ---

    @property
    def wraps_zero(self) -> bool:
        """True when the sector crosses the North direction (az = 0°)."""
        return self.az_max < self.az_min

    def contains_azimuth(self, az: float) -> bool:
        """Return True if *az* (degrees) falls within this sector."""
        az = az % 360.0
        if self.wraps_zero:
            return az >= self.az_min or az <= self.az_max
        return self.az_min <= az <= self.az_max

    @property
    def az_center(self) -> float:
        """Azimuth at the centre of the sector."""
        if self.wraps_zero:
            span = (self.az_max + 360.0 - self.az_min)
        else:
            span = self.az_max - self.az_min
        center = (self.az_min + span / 2.0) % 360.0
        return center

    def angular_distance_to_center(self, az: float, el: float) -> float:
        """
        Great-circle-like angular distance from (az, el) to sector centre
        (az_center, (el_min+el_max)/2).  Used for ranking.
        """
        el_center = (self.el_min + self.el_max) / 2.0
        az_c = self.az_center
        return _angular_sep_deg(az, el, az_c, el_center)

    def distance_to_hotspot(self, az: float, el: float) -> Optional[float]:
        """Return angular distance to hotspot (if defined)."""
        if self.hotspot_el is None or self.hotspot_az is None:
            return None
        return _angular_sep_deg(az, el, self.hotspot_az, self.hotspot_el)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "az_min": self.az_min,
            "az_max": self.az_max,
            "el_min": self.el_min,
            "el_max": self.el_max,
            "hotspot_el": self.hotspot_el,
            "hotspot_az": self.hotspot_az,
            "rising_el_min": self.rising_el_min,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SectorDefinition":
        return cls(
            name=d["name"],
            az_min=float(d["az_min"]),
            az_max=float(d["az_max"]),
            el_min=float(d["el_min"]),
            el_max=float(d["el_max"]),
            hotspot_el=d.get("hotspot_el"),
            hotspot_az=d.get("hotspot_az"),
            rising_el_min=d.get("rising_el_min"),
            enabled=bool(d.get("enabled", True)),
        )


# ---------------------------------------------------------------------------
# Magnitude bin
# ---------------------------------------------------------------------------


@dataclass
class MagnitudeBin:
    """
    A magnitude range and number of targets required per slot/sector.

    Bounds are exclusive: vmag_min < V < vmag_max.
    Use vmag_min = -99 to express "any magnitude brighter than vmag_max".
    """

    label: str          # e.g. "NGS_BRIGHT"
    target_type: str    # "NGS" | "LPC" — for output labelling only
    vmag_min: float     # exclusive lower bound (use -99 for unbounded)
    vmag_max: float     # exclusive upper bound
    required_count: int
    allow_reuse: bool = False   # may this bin reuse stars assigned to other bins?

    def contains(self, vmag: float) -> bool:
        return self.vmag_min < vmag < self.vmag_max

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "target_type": self.target_type,
            "vmag_min": self.vmag_min,
            "vmag_max": self.vmag_max,
            "required_count": self.required_count,
            "allow_reuse": self.allow_reuse,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MagnitudeBin":
        return cls(
            label=d["label"],
            target_type=d["target_type"],
            vmag_min=float(d["vmag_min"]),
            vmag_max=float(d["vmag_max"]),
            required_count=int(d["required_count"]),
            allow_reuse=bool(d.get("allow_reuse", False)),
        )


# ---------------------------------------------------------------------------
# Star candidate
# ---------------------------------------------------------------------------


@dataclass
class StarCandidate:
    """A star from the catalog with its basic astrometric and photometric properties.

    Multi-band magnitudes (U, B, R, I, J, H, K) are optional: ``None`` means
    the value was not available in the queried catalog. The primary magnitude
    used throughout the pipeline is selected via :meth:`mag_for_band`.
    """

    star_id: str          # catalog key, e.g. "HIP 71683"
    star_name: str        # human-readable name
    ra_deg: float         # J2000 right ascension [°]
    dec_deg: float        # J2000 declination [°]
    vmag: float           # Johnson V magnitude (always required)
    catalog_source: str   # "Hipparcos" | "2MASS" | "SIMBAD" | "local" | …
    spectral_type: str = ""
    # --------------- multi-band photometry (None = not available) ---------------
    umag: Optional[float] = None   # Johnson U
    bmag: Optional[float] = None   # Johnson B
    rmag: Optional[float] = None   # Cousins R
    imag: Optional[float] = None   # Cousins I
    jmag: Optional[float] = None   # 2MASS J
    hmag: Optional[float] = None   # 2MASS H
    kmag: Optional[float] = None   # 2MASS Ks

    # Mapping band letter → attribute name (used by mag_for_band)
    _BAND_ATTR: Dict[str, str] = field(
        default_factory=lambda: {
            "U": "umag", "B": "bmag", "V": "vmag",
            "R": "rmag", "I": "imag",
            "J": "jmag", "H": "hmag", "K": "kmag",
        },
        repr=False,
        compare=False,
    )

    def mag_for_band(self, band: str) -> Optional[float]:
        """Return the magnitude in *band* (e.g. 'V', 'J', 'K'), or None.

        Parameters
        ----------
        band : one of 'U', 'B', 'V', 'R', 'I', 'J', 'H', 'K'

        Returns
        -------
        float or None if the magnitude is not available for this star.
        """
        attr = self._BAND_ATTR.get(band.upper())
        if attr is None:
            return None
        return getattr(self, attr, None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "star_id": self.star_id,
            "star_name": self.star_name,
            "ra_deg": self.ra_deg,
            "dec_deg": self.dec_deg,
            "vmag": self.vmag,
            "catalog_source": self.catalog_source,
            "spectral_type": self.spectral_type,
            "umag": self.umag,
            "bmag": self.bmag,
            "rmag": self.rmag,
            "imag": self.imag,
            "jmag": self.jmag,
            "hmag": self.hmag,
            "kmag": self.kmag,
        }


# ---------------------------------------------------------------------------
# Selected target
# ---------------------------------------------------------------------------


@dataclass
class SelectedTarget:
    """A star that has been selected for a specific slot / sector / bin."""

    star: StarCandidate
    slot: TimeSlot
    sector: SectorDefinition
    mag_bin: MagnitudeBin
    alt_min_deg: float
    alt_mean_deg: float
    az_mean_deg: float
    visible_full_slot: bool
    repeated_from_previous_slot: bool = False
    hotspot_distance_deg: Optional[float] = None
    ranking_score: float = 0.0
    notes: str = ""

    def to_export_dict(self) -> Dict[str, Any]:
        """Produce flat dict for CSV/Excel export.

        All eight photometric bands are included; missing values are
        represented as empty strings for compatibility with Excel/CSV readers.
        """
        def _fmt_mag(v: Optional[float]) -> str:
            """Return magnitude rounded to 3 dp or empty string if missing."""
            return round(v, 3) if v is not None else ""

        return {
            "observing_night": self.slot.night_label,
            "slot_start_local": self.slot.start_local.strftime("%Y-%m-%d %H:%M"),
            "slot_end_local": self.slot.end_local.strftime("%Y-%m-%d %H:%M"),
            "slot_start_utc": self.slot.start_utc.strftime("%Y-%m-%d %H:%M"),
            "slot_end_utc": self.slot.end_utc.strftime("%Y-%m-%d %H:%M"),
            "sector": self.sector.name,
            "target_type": self.mag_bin.target_type,
            "mag_bin_label": self.mag_bin.label,
            "star_name": self.star.star_name,
            "star_id": self.star.star_id,
            "ra_deg": round(self.star.ra_deg, 5),
            "dec_deg": round(self.star.dec_deg, 5),
            # All photometric bands – empty string when unavailable
            "umag": _fmt_mag(self.star.umag),
            "bmag": _fmt_mag(self.star.bmag),
            "vmag": round(self.star.vmag, 3),
            "rmag": _fmt_mag(self.star.rmag),
            "imag": _fmt_mag(self.star.imag),
            "jmag": _fmt_mag(self.star.jmag),
            "hmag": _fmt_mag(self.star.hmag),
            "kmag": _fmt_mag(self.star.kmag),
            "alt_min_deg": round(self.alt_min_deg, 2),
            "alt_mean_deg": round(self.alt_mean_deg, 2),
            "az_mean_deg": round(self.az_mean_deg, 2),
            "visible_full_slot": "YES" if self.visible_full_slot else "NO",
            "repeated_from_previous_slot": "YES" if self.repeated_from_previous_slot else "NO",
            "hotspot_distance_deg": (
                round(self.hotspot_distance_deg, 2)
                if self.hotspot_distance_deg is not None
                else ""
            ),
            "ranking_score": round(self.ranking_score, 4),
            "notes": self.notes,
            "catalog_source": self.star.catalog_source,
        }


# ---------------------------------------------------------------------------
# Coverage summary
# ---------------------------------------------------------------------------


@dataclass
class SlotSectorCoverage:
    """Summary row for one slot + sector combination."""

    night_label: str
    slot_label: str
    slot_display: str
    sector_name: str
    fully_covered: bool
    targets_found: int
    targets_required: int
    missing_bins: List[str] = field(default_factory=list)

    def to_export_dict(self) -> Dict[str, Any]:
        return {
            "observing_night": self.night_label,
            "slot": self.slot_display,
            "sector": self.sector_name,
            "fully_covered": "YES" if self.fully_covered else "NO",
            "targets_found": self.targets_found,
            "targets_required": self.targets_required,
            "unsatisfied_bins": "; ".join(self.missing_bins) if self.missing_bins else "—",
        }


# ---------------------------------------------------------------------------
# Planning result
# ---------------------------------------------------------------------------


@dataclass
class PlanningResult:
    """Container for the complete output of a planning run."""

    slots: List[TimeSlot] = field(default_factory=list)
    selected_targets: List[SelectedTarget] = field(default_factory=list)
    coverage: List[SlotSectorCoverage] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total_targets(self) -> int:
        return len(self.selected_targets)

    @property
    def unsatisfied_slot_sectors(self) -> int:
        return sum(1 for c in self.coverage if not c.fully_covered)


# ---------------------------------------------------------------------------
# Full application config (serialisable)
# ---------------------------------------------------------------------------


@dataclass
class AppConfig:
    """
    Complete application configuration — can be saved/loaded as JSON.
    """

    observatory: ObservatoryConfig
    session: ObservingSession
    sectors: List[SectorDefinition]
    magnitude_bins: List[MagnitudeBin]
    catalog_source: str = "vizier"          # "vizier" | "local"
    local_catalog_path: str = ""
    allow_global_reuse: bool = False        # reuse stars across bins in same slot+sector
    catalog_vmag_limit: float = 7.5         # pre-filter catalogue magnitude limit (V)
    catalog_band: str = "V"                 # photometric band for filtering: U/B/V/R/I/J/H/K
    visibility_sample_minutes: int = 10     # how often to sample alt/az within a slot
    min_dec_filter: float = -15.0           # pre-filter: max dec to query
    max_dec_filter: float = 70.0            # pre-filter: min dec to query

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observatory": self.observatory.to_dict(),
            "session": self.session.to_dict(),
            "sectors": [s.to_dict() for s in self.sectors],
            "magnitude_bins": [b.to_dict() for b in self.magnitude_bins],
            "catalog_source": self.catalog_source,
            "local_catalog_path": self.local_catalog_path,
            "allow_global_reuse": self.allow_global_reuse,
            "catalog_vmag_limit": self.catalog_vmag_limit,
            "catalog_band": self.catalog_band,
            "visibility_sample_minutes": self.visibility_sample_minutes,
            "min_dec_filter": self.min_dec_filter,
            "max_dec_filter": self.max_dec_filter,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AppConfig":
        return cls(
            observatory=ObservatoryConfig.from_dict(d["observatory"]),
            session=ObservingSession.from_dict(d["session"]),
            sectors=[SectorDefinition.from_dict(s) for s in d["sectors"]],
            magnitude_bins=[MagnitudeBin.from_dict(b) for b in d["magnitude_bins"]],
            catalog_source=d.get("catalog_source", "vizier"),
            local_catalog_path=d.get("local_catalog_path", ""),
            allow_global_reuse=bool(d.get("allow_global_reuse", False)),
            catalog_vmag_limit=float(d.get("catalog_vmag_limit", 7.5)),
            catalog_band=d.get("catalog_band", "V"),
            visibility_sample_minutes=int(d.get("visibility_sample_minutes", 10)),
            min_dec_filter=float(d.get("min_dec_filter", -15.0)),
            max_dec_filter=float(d.get("max_dec_filter", 70.0)),
        )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _angular_sep_deg(az1: float, el1: float, az2: float, el2: float) -> float:
    """
    Approximate angular separation on the sphere (degrees).
    Uses the spherical law of cosines where az→longitude, el→latitude.
    """
    d_az = math.radians(az2 - az1)
    lat1, lat2 = math.radians(el1), math.radians(el2)
    cos_sep = (
        math.sin(lat1) * math.sin(lat2)
        + math.cos(lat1) * math.cos(lat2) * math.cos(d_az)
    )
    cos_sep = max(-1.0, min(1.0, cos_sep))
    return math.degrees(math.acos(cos_sep))
