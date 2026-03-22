"""
Input validation helpers for StarVisibility.
Returns human-readable error messages suitable for displaying in the GUI.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple


def validate_date_string(value: str, field_name: str = "date") -> Optional[str]:
    """Return an error message or None if valid ISO date string."""
    try:
        date.fromisoformat(value.strip())
        return None
    except ValueError:
        return f"{field_name}: expected YYYY-MM-DD, got {value!r}"


def validate_date_range(start: str, end: str) -> Optional[str]:
    """Ensure start_night <= end_night."""
    err = validate_date_string(start, "start_night") or validate_date_string(end, "end_night")
    if err:
        return err
    if date.fromisoformat(end) < date.fromisoformat(start):
        return "end_night must be equal to or after start_night."
    return None


def validate_hhmm(value: str, field_name: str = "time") -> Optional[str]:
    """Validate HH:MM string."""
    parts = value.strip().split(":")
    try:
        if len(parts) != 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError
        return None
    except (ValueError, AttributeError):
        return f"{field_name}: expected HH:MM (e.g. 20:00), got {value!r}"


def validate_float_range(
    value: str,
    lo: float,
    hi: float,
    field_name: str,
    allow_equal_lo: bool = True,
    allow_equal_hi: bool = True,
) -> Optional[str]:
    """Validate that a string parses to a float within [lo, hi]."""
    try:
        v = float(value)
    except (ValueError, TypeError):
        return f"{field_name}: must be a number."
    ok_lo = v >= lo if allow_equal_lo else v > lo
    ok_hi = v <= hi if allow_equal_hi else v < hi
    if not (ok_lo and ok_hi):
        return f"{field_name}: must be between {lo} and {hi}, got {v}."
    return None


def validate_positive_float(value: str, field_name: str) -> Optional[str]:
    """Validate that a string is a positive float."""
    try:
        v = float(value)
        if v <= 0:
            raise ValueError
        return None
    except (ValueError, TypeError):
        return f"{field_name}: must be a positive number, got {value!r}."


def validate_positive_int(value: str, field_name: str) -> Optional[str]:
    """Validate that a string is a positive integer."""
    try:
        v = int(value)
        if v < 1:
            raise ValueError
        return None
    except (ValueError, TypeError):
        return f"{field_name}: must be a positive integer, got {value!r}."


def validate_azimuth(value: str, field_name: str) -> Optional[str]:
    """Validate azimuth in degrees [0, 360)."""
    return validate_float_range(value, 0.0, 360.0, field_name)


def validate_elevation(value: str, field_name: str) -> Optional[str]:
    """Validate elevation in degrees [0, 90]."""
    return validate_float_range(value, 0.0, 90.0, field_name)


def validate_local_catalog_path(path: str) -> Optional[str]:
    """Check that the file exists and has a supported extension."""
    if not path:
        return "local_catalog_path: path is empty."
    p = Path(path)
    if not p.exists():
        return f"local_catalog_path: file not found: {path!r}"
    if p.suffix.lower() not in {".csv", ".fits", ".fit", ".fz"}:
        return f"local_catalog_path: unsupported file type {p.suffix!r} (use .csv or .fits)."
    return None


def validate_magnitude_bins(bins_data: list) -> List[str]:
    """
    Validate a list of magnitude bin dicts/dataclasses.
    Returns a list of error strings (empty = no errors).
    """
    errors: List[str] = []
    labels_seen: set = set()
    for i, b in enumerate(bins_data):
        prefix = f"Bin #{i+1} ({getattr(b, 'label', '?')})"
        label = getattr(b, "label", "")
        if not label:
            errors.append(f"{prefix}: label is empty.")
        elif label in labels_seen:
            errors.append(f"{prefix}: duplicate label {label!r}.")
        else:
            labels_seen.add(label)

        vmag_min = getattr(b, "vmag_min", None)
        vmag_max = getattr(b, "vmag_max", None)
        if vmag_min is not None and vmag_max is not None:
            if vmag_min >= vmag_max:
                errors.append(f"{prefix}: vmag_min ({vmag_min}) must be < vmag_max ({vmag_max}).")

        req = getattr(b, "required_count", None)
        if req is not None and int(req) < 1:
            errors.append(f"{prefix}: required_count must be ≥ 1.")
    return errors


def collect_errors(*error_or_none: Optional[str]) -> List[str]:
    """Collect non-None error strings into a list."""
    return [e for e in error_or_none if e is not None]
