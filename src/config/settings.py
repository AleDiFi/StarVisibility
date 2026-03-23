"""
Application-level settings and constants.

Scientific assumptions documented here:
- AltAz azimuth: North=0°, East=90°, South=180°, West=270° (FITS/astropy standard).
- The North sector (315°–45°) wraps through 0°; handled via wraps_zero logic.
- Elevation check: sampled every VISIBILITY_SAMPLE_MINUTES across the slot;
  the star must stay above el_min at ALL sample points to be marked
  visible_full_slot=True.
- East rising rule: if rising_el_min is set for a sector, a star is also
  accepted when it is currently rising (alt increasing) and its minimum
  elevation during the slot is >= rising_el_min.
- South hotspot: targets are ranked by angular distance to (AZ=170°, EL=70°);
  closer = higher ranking bonus.
- Magnitude bins have exclusive bounds (vmag_min < V < vmag_max).
  Stars in the overlap region (5 < V < 6) qualify for both NGS_FAINT and LPC;
  by default they are assigned to the first bin that claims them.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

def _get_app_root() -> Path:
    """Return the base directory for runtime-generated files.

    - Source run: repository root (so dev runs behave as before)
    - Frozen executable (PyInstaller): directory containing the .exe
      (portable and writable, avoids temp/bundle paths)
    """
    if getattr(sys, "frozen", False):  # set by PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


PROJECT_ROOT = _get_app_root()
CACHE_DIR = PROJECT_ROOT / ".cache"
LOG_DIR = PROJECT_ROOT / "logs"
OUTPUT_DIR = PROJECT_ROOT / "output"

for _d in (CACHE_DIR, LOG_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

HIPPARCOS_CACHE_FILE = CACHE_DIR / "hipparcos_vmag7.5_cache.csv"
LOG_FILE = LOG_DIR / "starvisibility.log"

# ---------------------------------------------------------------------------
# Catalog settings
# ---------------------------------------------------------------------------

# VizieR catalog for Hipparcos (I/239/hip_main)
VIZIER_CATALOG_ID = "I/239/hip_main"
VIZIER_COLUMNS = ["HIP", "RAICRS", "DEICRS", "Vmag", "SpType"]
VIZIER_SERVER = "https://vizier.cds.unistra.fr"

# Fallback: Yale Bright Star Catalogue
VIZIER_BSC_ID = "V/50/catalog"

# Local catalog expected CSV column names (user-supplied file)
LOCAL_CATALOG_REQUIRED_COLS = ["ra_deg", "dec_deg", "vmag"]
LOCAL_CATALOG_OPTIONAL_COLS = ["star_id", "star_name", "spectral_type"]

# ---------------------------------------------------------------------------
# Computation settings
# ---------------------------------------------------------------------------

# Number of time samples per slot for visibility check (every N minutes by default)
DEFAULT_VISIBILITY_SAMPLE_MINUTES = 10

# Minimum number of catalog stars that triggers a warning
MIN_CATALOG_STARS_WARNING = 100

# ---------------------------------------------------------------------------
# GUI settings
# ---------------------------------------------------------------------------

APP_TITLE = "StarVisibility – Astronomical Target Planner"
APP_VERSION = "1.0.0"
APP_AUTHOR = "INAF / OGS CaNaPy Team"

WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800

# Status labels
STATUS_READY = "Ready"
STATUS_RUNNING = "Running…"
STATUS_DONE = "Done"
STATUS_FAILED = "Failed"

# ---------------------------------------------------------------------------
# Export settings
# ---------------------------------------------------------------------------

# UTF-8 BOM ensures Excel opens the CSV correctly on all platforms
CSV_ENCODING = "utf-8-sig"
CSV_SEPARATOR = ","
EXCEL_SHEET_TARGETS = "Targets"
EXCEL_SHEET_SUMMARY = "Summary"

# ---------------------------------------------------------------------------
# Ranking weights (used in core/ranking.py)
# ---------------------------------------------------------------------------

RANK_FULL_VISIBILITY_BONUS = 1000.0
RANK_ALT_WEIGHT = 1.0          # per degree of mean elevation
RANK_AZ_CENTER_PENALTY = 0.3   # per degree from sector azimuth centre
RANK_HOTSPOT_BONUS_MAX = 100.0 # max bonus for being exactly on hotspot
RANK_HOTSPOT_SCALE = 20.0      # hotspot bonus = max * exp(-dist/scale)
RANK_REPEAT_PENALTY = 80.0     # penalty if star already selected in prev slot
