"""
Tests for sector geometry logic.
"""

import pytest
from src.models.domain import SectorDefinition


def make_sector(name, az_min, az_max, el_min=60, el_max=90,
                hotspot_el=None, hotspot_az=None, rising_el_min=None):
    return SectorDefinition(
        name=name, az_min=az_min, az_max=az_max,
        el_min=el_min, el_max=el_max,
        hotspot_el=hotspot_el, hotspot_az=hotspot_az,
        rising_el_min=rising_el_min,
    )


class TestSectorWrapsZero:
    """North sector (315–45) crosses az=0°."""

    def test_wraps_zero_true_for_north(self):
        s = make_sector("North", az_min=315, az_max=45)
        assert s.wraps_zero is True

    def test_wraps_zero_false_for_south(self):
        s = make_sector("South", az_min=135, az_max=225)
        assert s.wraps_zero is False

    def test_north_contains_0(self):
        s = make_sector("North", az_min=315, az_max=45)
        assert s.contains_azimuth(0.0)

    def test_north_contains_360(self):
        s = make_sector("North", az_min=315, az_max=45)
        assert s.contains_azimuth(360.0)

    def test_north_contains_350(self):
        s = make_sector("North", az_min=315, az_max=45)
        assert s.contains_azimuth(350.0)

    def test_north_contains_20(self):
        s = make_sector("North", az_min=315, az_max=45)
        assert s.contains_azimuth(20.0)

    def test_north_does_not_contain_90(self):
        s = make_sector("North", az_min=315, az_max=45)
        assert not s.contains_azimuth(90.0)

    def test_north_does_not_contain_180(self):
        s = make_sector("North", az_min=315, az_max=45)
        assert not s.contains_azimuth(180.0)


class TestSectorStandard:
    """Standard (non-wrapping) sectors."""

    def test_south_contains_170(self):
        s = make_sector("South", az_min=135, az_max=225)
        assert s.contains_azimuth(170.0)

    def test_south_contains_180(self):
        s = make_sector("South", az_min=135, az_max=225)
        assert s.contains_azimuth(180.0)

    def test_south_does_not_contain_90(self):
        s = make_sector("South", az_min=135, az_max=225)
        assert not s.contains_azimuth(90.0)

    def test_east_contains_90(self):
        s = make_sector("East", az_min=45, az_max=135)
        assert s.contains_azimuth(90.0)

    def test_west_contains_270(self):
        s = make_sector("West", az_min=225, az_max=315)
        assert s.contains_azimuth(270.0)


class TestSectorCenter:
    """Azimuth center calculation."""

    def test_south_center(self):
        s = make_sector("South", az_min=135, az_max=225)
        assert abs(s.az_center - 180.0) < 0.01

    def test_east_center(self):
        s = make_sector("East", az_min=45, az_max=135)
        assert abs(s.az_center - 90.0) < 0.01

    def test_north_center(self):
        # North: 315–45 → center at 0° (or 360°)
        s = make_sector("North", az_min=315, az_max=45)
        center = s.az_center % 360
        assert abs(center - 0.0) < 0.01 or abs(center - 360.0) < 0.01


class TestSectorHotspot:
    """Hotspot distance calculation."""

    def test_hotspot_distance_zero_at_hotspot(self):
        s = make_sector("South", 135, 225, hotspot_el=70, hotspot_az=170)
        d = s.distance_to_hotspot(az=170.0, el=70.0)
        assert d is not None
        assert d < 0.01  # essentially zero

    def test_hotspot_distance_positive_away(self):
        s = make_sector("South", 135, 225, hotspot_el=70, hotspot_az=170)
        d = s.distance_to_hotspot(az=180.0, el=75.0)
        assert d is not None
        assert d > 0

    def test_no_hotspot_returns_none(self):
        s = make_sector("North", 315, 45)
        assert s.distance_to_hotspot(0.0, 80.0) is None
