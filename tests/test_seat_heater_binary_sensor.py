"""Tests for the seat heater binary sensors.

The library reports seat status as a string ("Off", "Low Heat", ...), and any
non-empty string is truthy, so passing it through made "Off" read as on.
"""

import pytest
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo.binary_sensor import (
    SENSOR_DESCRIPTIONS,
    HyundaiKiaBinarySensorEntityDescription,
)

SEAT_KEYS = {
    "front_left_seat_heater_on": "front_left_seat_status",
    "front_right_seat_heater_on": "front_right_seat_status",
    "rear_left_seat_heater_on": "rear_left_seat_status",
    "rear_right_seat_heater_on": "rear_right_seat_status",
}


def _description(key: str) -> HyundaiKiaBinarySensorEntityDescription:
    return next(d for d in SENSOR_DESCRIPTIONS if d.key == key)


@pytest.mark.parametrize("key", SEAT_KEYS)
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (None, None),
        ("Off", False),
        ("On", True),
        ("Low Heat", True),
        ("Medium Heat", True),
        ("High Heat", True),
        ("Low Cool", False),
        ("Medium Cool", False),
        ("High Cool", False),
    ],
)
def test_seat_heater_is_on(key: str, status: str | None, expected: bool | None) -> None:
    vehicle = Vehicle()
    setattr(vehicle, SEAT_KEYS[key], status)
    is_on = _description(key).is_on
    assert is_on is not None
    assert is_on(vehicle) is expected
