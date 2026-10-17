"""Out-of-range battery percentages must surface as unknown, not as bogus values.

Regression for kia_uvo #1935: an EU IONIQ 5 reported SoH Ratio 255 after a BMS
OTA update, which the sensor published as 255 %.
"""

import pytest

from custom_components.kia_uvo.sensor import _sanitize_percentage


@pytest.mark.parametrize("key", ["ev_battery_soh_percentage", "ev_battery_percentage", "car_battery_percentage"])
@pytest.mark.parametrize("value", [0, 1, 99.5, 100])
def test_in_range_values_pass_through(key, value):
    assert _sanitize_percentage(key, value) == value


@pytest.mark.parametrize("key", ["ev_battery_soh_percentage", "ev_battery_percentage"])
@pytest.mark.parametrize("value", [255, 101, -1, -0.5])
def test_out_of_range_values_become_unknown(key, value):
    assert _sanitize_percentage(key, value) is None


def test_none_and_non_numeric_are_untouched():
    assert _sanitize_percentage("ev_battery_soh_percentage", None) is None
    assert _sanitize_percentage("ev_battery_soh_percentage", "unknown") == "unknown"
    assert _sanitize_percentage("ev_battery_soh_percentage", True) is True


def test_other_keys_are_not_sanitized():
    assert _sanitize_percentage("ev_battery_remain", 255) == 255
