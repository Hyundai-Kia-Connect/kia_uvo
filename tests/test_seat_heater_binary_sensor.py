"""Tests for the seat-heater binary sensors.

Their keys (``*_seat_heater_on``) are not Vehicle attributes, so creation
must be gated on the matching ``*_seat_status`` instead of the key, and the
state derived from the status string ("Off" is a truthy string).
"""

from typing import Any

import pytest
from conftest import make_coordinator, make_hass
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo import binary_sensor as binary_sensor_platform


async def _setup(vehicle: Vehicle) -> dict[str, Any]:
    hass, config_entry = make_hass(make_coordinator(vehicle))
    created: list[Any] = []
    await binary_sensor_platform.async_setup_entry(hass, config_entry, created.extend)
    return {entity.entity_description.key: entity for entity in created}


async def test_seat_heater_sensor_created_from_seat_status() -> None:
    """A reported seat status creates the matching seat-heater sensor."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.front_left_seat_status = "Off"
    created = await _setup(vehicle)
    assert "front_left_seat_heater_on" in created
    assert "front_right_seat_heater_on" not in created


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Off", False),
        ("On", True),
        ("Low Heat", True),
        ("High Heat", True),
        ("Medium Cool", True),
        (None, None),
    ],
)
async def test_seat_heater_state(status: str | None, expected: bool | None) -> None:
    """Any heating or cooling level is on; only "Off" is off."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.rear_right_seat_status = "Off"
    entity = (await _setup(vehicle))["rear_right_seat_heater_on"]
    vehicle.rear_right_seat_status = status
    assert entity.is_on is expected
