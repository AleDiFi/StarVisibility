"""
CSV export for StarVisibility.

Produces two CSV files:
  1. targets_<timestamp>.csv   – one row per selected target (full detail)
  2. summary_<timestamp>.csv   – one row per slot+sector (coverage overview)

Both files use UTF-8 BOM encoding (utf-8-sig) so Excel opens them correctly
without needing to set the encoding manually.

Column order follows the specification in the project requirements.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.config.settings import CSV_ENCODING, CSV_SEPARATOR, OUTPUT_DIR
from src.models.domain import PlanningResult, SelectedTarget, SlotSectorCoverage
from src.utils.logging_utils import get_logger

log = get_logger("csv_exporter")

# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

TARGET_COLUMNS = [
    "observing_night",
    "slot_start_local",
    "slot_end_local",
    "slot_start_utc",
    "slot_end_utc",
    "sector",
    "target_type",
    "mag_bin_label",
    "star_name",
    "star_id",
    "ra_deg",
    "dec_deg",
    # All photometric bands; empty string when data not available
    "vmag",
    "umag",
    "bmag",
    "rmag",
    "imag",
    "jmag",
    "hmag",
    "kmag",
    "alt_min_deg",
    "alt_mean_deg",
    "az_mean_deg",
    "visible_full_slot",
    "repeated_from_previous_slot",
    "hotspot_distance_deg",
    "ranking_score",
    "notes",
    "catalog_source",
]

SUMMARY_COLUMNS = [
    "observing_night",
    "slot",
    "sector",
    "fully_covered",
    "targets_found",
    "targets_required",
    "unsatisfied_bins",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_targets_csv(
    targets: List[SelectedTarget],
    output_path: Optional[Path] = None,
) -> Path:
    """
    Write the full targets CSV and return the path of the created file.

    Parameters
    ----------
    targets : list of SelectedTarget
    output_path : explicit path; if None a timestamped file is created in OUTPUT_DIR

    Returns
    -------
    Path of the written file
    """
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"targets_{ts}.csv"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort by night → slot_index → sector → mag_bin
    sorted_targets = sorted(
        targets,
        key=lambda t: (
            t.slot.night_label,
            t.slot.slot_index,
            t.sector.name,
            t.mag_bin.label,
        ),
    )

    with open(output_path, "w", newline="", encoding=CSV_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_COLUMNS, delimiter=CSV_SEPARATOR,
                                extrasaction="ignore")
        writer.writeheader()
        for target in sorted_targets:
            writer.writerow(target.to_export_dict())

    log.info("Targets CSV written: %s (%d rows)", output_path, len(sorted_targets))
    return output_path


def export_summary_csv(
    coverage: List[SlotSectorCoverage],
    output_path: Optional[Path] = None,
) -> Path:
    """
    Write the summary CSV and return the path.

    Parameters
    ----------
    coverage : list of SlotSectorCoverage
    output_path : explicit path; if None a timestamped file is created

    Returns
    -------
    Path of the written file
    """
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"summary_{ts}.csv"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sorted_coverage = sorted(
        coverage,
        key=lambda c: (c.night_label, c.slot_label, c.sector_name),
    )

    with open(output_path, "w", newline="", encoding=CSV_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS, delimiter=CSV_SEPARATOR,
                                extrasaction="ignore")
        writer.writeheader()
        for cov in sorted_coverage:
            writer.writerow(cov.to_export_dict())

    log.info("Summary CSV written: %s (%d rows)", output_path, len(sorted_coverage))
    return output_path


def export_planning_result(
    result: PlanningResult,
    output_dir: Optional[Path] = None,
) -> tuple[Path, Path]:
    """
    Export both CSVs for a PlanningResult.

    Returns
    -------
    (targets_path, summary_path)
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    targets_path = export_targets_csv(
        result.selected_targets, output_dir / f"targets_{ts}.csv"
    )
    summary_path = export_summary_csv(
        result.coverage, output_dir / f"summary_{ts}.csv"
    )
    return targets_path, summary_path
