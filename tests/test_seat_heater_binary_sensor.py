"""Tests for the seat heater binary sensors.

The library reports seat status as a string ("Off", "Low Heat", ...), and any
non-empty string is truthy, so passing it through made "Off" read as on.
"""

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import SEAT_STATUS
import pytest

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
    ("code", "expected"),
    [
        (None, None),
        (0, False),  # Off
        (1, True),  # On
        (2, False),  # Off
        (3, False),  # Low Cool
        (4, False),  # Medium Cool
        (5, False),  # High Cool
        (6, True),  # Low Heat
        (7, True),  # Medium Heat
        (8, True),  # High Heat
    ],
)
def test_seat_heater_is_on(key: str, code: int | None, expected: bool | None) -> None:
    vehicle = Vehicle(id="v1")
    setattr(vehicle, SEAT_KEYS[key], SEAT_STATUS[code])
    is_on = _description(key).is_on
    assert is_on is not None
    assert is_on(vehicle) is expected
