"""
Date / time utilities for StarVisibility.

All internal scheduling logic uses UTC-aware datetime objects.
The observer's local time is only used for display and for parsing
user-supplied sunset/sunrise strings.

Assumption: "night of YYYY-MM-DD" means sunset on that date followed by
sunrise on the next calendar day.  Slots may cross midnight (UTC or local).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_timezone(tz_name: str) -> ZoneInfo:
    """
    Return a ZoneInfo object for *tz_name*.
    Raises ValueError if the timezone is not recognised.
    """
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {tz_name!r}") from exc


def parse_hhmm(time_str: str) -> Tuple[int, int]:
    """
    Parse "HH:MM" into (hour, minute).  Raises ValueError on bad input.
    """
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Expected HH:MM, got {time_str!r}")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"Invalid time {time_str!r}")
    return h, m


def local_to_utc(local_dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert a local (tz-aware or naïve) datetime to UTC-aware datetime."""
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


def utc_to_local(utc_dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert a UTC-aware datetime to the given local timezone."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(tz)


def night_window_utc(
    night_date: date,
    sunset_local: str,
    sunrise_local: str,
    tz: ZoneInfo,
) -> Tuple[datetime, datetime]:
    """
    Return (sunset_utc, sunrise_utc) for the night starting on *night_date*.

    Sunset is on the evening of *night_date* (local time).
    Sunrise is on the morning of the *following* calendar day (local time).

    Both returned datetimes are UTC-aware.
    """
    sh, sm = parse_hhmm(sunset_local)
    rh, rm = parse_hhmm(sunrise_local)

    sunset_local_dt = datetime(night_date.year, night_date.month, night_date.day,
                               sh, sm, tzinfo=tz)

    # Sunrise is always on the next calendar day
    next_day = night_date + timedelta(days=1)
    sunrise_local_dt = datetime(next_day.year, next_day.month, next_day.day,
                                rh, rm, tzinfo=tz)

    return sunset_local_dt.astimezone(timezone.utc), sunrise_local_dt.astimezone(timezone.utc)


def iter_nights(start_iso: str, end_iso: str) -> List[date]:
    """
    Return a list of date objects from *start_iso* to *end_iso* inclusive.
    Both arguments must be ISO-format date strings "YYYY-MM-DD".
    """
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    if end < start:
        raise ValueError(f"end_night ({end_iso}) is before start_night ({start_iso})")
    nights: List[date] = []
    current = start
    while current <= end:
        nights.append(current)
        current += timedelta(days=1)
    return nights


def build_time_slots(
    sunset_utc: datetime,
    sunrise_utc: datetime,
    slot_duration_hours: float,
    tz: ZoneInfo,
    night_label: str,
    slot_step_hours: Optional[float] = None,
) -> List[Tuple[int, datetime, datetime, datetime, datetime]]:
    """
    Divide the night window into (possibly overlapping) slots.

    When *slot_step_hours* is smaller than *slot_duration_hours* the slots
    form a sliding window (start advances by *step*, duration stays fixed).
    When *slot_step_hours* is None or equal to *slot_duration_hours* the
    behaviour is identical to the original non-overlapping blocks.

    Returns a list of tuples:
        (slot_index, start_utc, end_utc, start_local, end_local)

    The last slot may be shorter than *slot_duration_hours* if it reaches
    sunrise before its natural end.
    """
    if slot_step_hours is None or slot_step_hours <= 0:
        slot_step_hours = slot_duration_hours

    step = timedelta(hours=slot_step_hours)
    duration = timedelta(hours=slot_duration_hours)
    slots = []
    current = sunset_utc
    idx = 0
    while current < sunrise_utc:
        end = min(current + duration, sunrise_utc)
        start_local = utc_to_local(current, tz)
        end_local = utc_to_local(end, tz)
        slots.append((idx, current, end, start_local, end_local))
        current = current + step
        idx += 1
    return slots


def format_night_label(d: date) -> str:
    """Return "YYYY-MM-DD" string for a date (used as night identifier)."""
    return d.isoformat()


def sample_times_in_slot(
    start_utc: datetime,
    end_utc: datetime,
    sample_minutes: int,
) -> List[datetime]:
    """
    Return evenly-spaced UTC datetimes within [start_utc, end_utc].
    Always includes the start and end.
    """
    total_seconds = (end_utc - start_utc).total_seconds()
    step = timedelta(minutes=sample_minutes).total_seconds()
    n = max(2, int(total_seconds / step) + 1)
    times = []
    for i in range(n):
        t = start_utc + timedelta(seconds=i * total_seconds / (n - 1))
        times.append(t)
    return times
