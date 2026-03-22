"""
Tests for time slot generation.
"""

import pytest
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from src.utils.datetime_utils import (
    build_time_slots,
    iter_nights,
    night_window_utc,
    parse_hhmm,
    sample_times_in_slot,
)


TZ_MADRID = ZoneInfo("Europe/Madrid")


class TestParseHHMM:
    def test_valid(self):
        assert parse_hhmm("20:00") == (20, 0)
        assert parse_hhmm("08:30") == (8, 30)

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_hhmm("2000")

    def test_invalid_hour(self):
        with pytest.raises(ValueError):
            parse_hhmm("25:00")

    def test_invalid_minute(self):
        with pytest.raises(ValueError):
            parse_hhmm("20:60")


class TestIterNights:
    def test_single_night(self):
        nights = iter_nights("2026-04-02", "2026-04-02")
        assert len(nights) == 1
        assert nights[0] == date(2026, 4, 2)

    def test_range(self):
        nights = iter_nights("2026-04-02", "2026-04-12")
        assert len(nights) == 11
        assert nights[0] == date(2026, 4, 2)
        assert nights[-1] == date(2026, 4, 12)

    def test_end_before_start_raises(self):
        with pytest.raises(ValueError):
            iter_nights("2026-04-12", "2026-04-02")


class TestNightWindow:
    def test_sunset_before_sunrise(self):
        sunset, sunrise = night_window_utc(
            date(2026, 4, 2), "20:00", "08:00", TZ_MADRID
        )
        assert sunset < sunrise

    def test_sunrise_next_day(self):
        sunset, sunrise = night_window_utc(
            date(2026, 4, 2), "20:00", "08:00", TZ_MADRID
        )
        # Sunrise should be on April 3 (next calendar day)
        # In Europe/Madrid UTC+2 in summer or UTC+1 in April:
        # 08:00 local on Apr 3 = 07:00 or 06:00 UTC
        sunrise_date = sunrise.date()
        assert sunrise_date == date(2026, 4, 3)

    def test_duration_approximately_12h(self):
        sunset, sunrise = night_window_utc(
            date(2026, 4, 2), "20:00", "08:00", TZ_MADRID
        )
        duration_hours = (sunrise - sunset).total_seconds() / 3600
        # Should be 12 hours
        assert abs(duration_hours - 12.0) < 0.1


class TestBuildTimeSlots:
    def test_six_slots_in_12h(self):
        tz = TZ_MADRID
        night = date(2026, 4, 2)
        sunset, sunrise = night_window_utc(night, "20:00", "08:00", tz)
        slots = build_time_slots(sunset, sunrise, 2.0, tz, "2026-04-02")
        assert len(slots) == 6

    def test_slots_are_contiguous(self):
        tz = TZ_MADRID
        night = date(2026, 4, 2)
        sunset, sunrise = night_window_utc(night, "20:00", "08:00", tz)
        slots = build_time_slots(sunset, sunrise, 2.0, tz, "2026-04-02")
        for i in range(len(slots) - 1):
            _, _, end_this, _, _ = slots[i]
            _, _, start_next, _, _ = slots[i + 1]
            assert end_this == start_next

    def test_first_slot_starts_at_sunset(self):
        tz = TZ_MADRID
        night = date(2026, 4, 2)
        sunset, sunrise = night_window_utc(night, "20:00", "08:00", tz)
        slots = build_time_slots(sunset, sunrise, 2.0, tz, "2026-04-02")
        _, start, _, _, _ = slots[0]
        assert start == sunset

    def test_last_slot_ends_at_sunrise(self):
        tz = TZ_MADRID
        night = date(2026, 4, 2)
        sunset, sunrise = night_window_utc(night, "20:00", "08:00", tz)
        slots = build_time_slots(sunset, sunrise, 2.0, tz, "2026-04-02")
        _, _, end, _, _ = slots[-1]
        assert end == sunrise


class TestSampleTimes:
    def test_includes_start_and_end(self):
        start = datetime(2026, 4, 2, 20, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 2, 22, 0, tzinfo=timezone.utc)
        times = sample_times_in_slot(start, end, sample_minutes=10)
        assert times[0] == start
        assert times[-1] == end

    def test_minimum_two_samples(self):
        start = datetime(2026, 4, 2, 20, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 2, 20, 5, tzinfo=timezone.utc)
        times = sample_times_in_slot(start, end, sample_minutes=30)
        assert len(times) >= 2

    def test_samples_in_2h_slot(self):
        start = datetime(2026, 4, 2, 20, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 2, 22, 0, tzinfo=timezone.utc)
        # 2 hours at 10 min → 13 samples (0, 10, 20, ..., 120 min)
        times = sample_times_in_slot(start, end, sample_minutes=10)
        assert len(times) == 13
