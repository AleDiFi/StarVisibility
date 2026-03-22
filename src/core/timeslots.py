"""
Time slot generation for StarVisibility.

Builds ordered lists of TimeSlot objects from the campaign settings,
correctly handling the midnight crossing.
"""

from __future__ import annotations

from datetime import date
from typing import List

from src.models.domain import AppConfig, ObservingSession, TimeSlot
from src.utils.datetime_utils import (
    build_time_slots,
    format_night_label,
    get_timezone,
    iter_nights,
    night_window_utc,
)


def generate_time_slots(config: AppConfig) -> List[TimeSlot]:
    """
    Generate all TimeSlot objects for the observing campaign.

    Slots are created for each night in [start_night, end_night].
    For each night, the window runs from sunset_local to sunrise_local
    (next calendar day) and is divided into equal blocks of
    slot_duration_hours.  The last block may be truncated to sunrise.

    Parameters
    ----------
    config : AppConfig

    Returns
    -------
    list of TimeSlot in chronological order
    """
    tz = get_timezone(config.observatory.timezone)
    session = config.session
    nights: List[date] = iter_nights(session.start_night, session.end_night)

    all_slots: List[TimeSlot] = []

    for night_date in nights:
        label = format_night_label(night_date)
        sunset_utc, sunrise_utc = night_window_utc(
            night_date,
            session.sunset_local,
            session.sunrise_local,
            tz,
        )

        raw_slots = build_time_slots(
            sunset_utc=sunset_utc,
            sunrise_utc=sunrise_utc,
            slot_duration_hours=session.slot_duration_hours,
            tz=tz,
            night_label=label,
            slot_step_hours=session.slot_step_hours,
        )

        for idx, s_utc, e_utc, s_local, e_local in raw_slots:
            all_slots.append(
                TimeSlot(
                    night_label=label,
                    slot_index=idx,
                    start_utc=s_utc,
                    end_utc=e_utc,
                    start_local=s_local,
                    end_local=e_local,
                )
            )

    return all_slots
