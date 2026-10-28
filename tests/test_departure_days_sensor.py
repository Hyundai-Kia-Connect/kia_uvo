"""Tests for departure days sensor creation and display formatting."""

import datetime as dt

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES


async def test_departure_days_sensor_formats_configured_days(setup_sensors) -> None:
    """Sensor formats a list of repeat days as a comma-separated string."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.engine_type = ENGINE_TYPES.EV
    vehicle.ev_first_departure_enabled = True
    vehicle.ev_first_departure_days = [1, 2, 3, 4, 5]
    vehicle.ev_first_departure_time = dt.time(7, 30)

    entities = await setup_sensors(vehicle)
    sensor = entities.get("ev_first_departure_days")
    assert sensor is not None
    assert sensor.native_value == "1, 2, 3, 4, 5"


async def test_departure_days_sensor_formats_empty_days_as_none(setup_sensors) -> None:
    """Sensor formats empty repeat days as 'None' instead of empty/unavailable."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.engine_type = ENGINE_TYPES.EV
    vehicle.ev_first_departure_enabled = True
    vehicle.ev_first_departure_days = []
    vehicle.ev_first_departure_time = dt.time(8, 0)

    entities = await setup_sensors(vehicle)
    sensor = entities.get("ev_first_departure_days")
    assert sensor is not None
    assert sensor.native_value == "None"


async def test_departure_days_sensor_formats_none_days_as_none(setup_sensors) -> None:
    """Sensor formats None repeat days as 'None' when departure schedule exists."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.engine_type = ENGINE_TYPES.EV
    vehicle.ev_second_departure_enabled = False
    vehicle.ev_second_departure_days = None
    vehicle.ev_second_departure_time = dt.time(9, 0)

    entities = await setup_sensors(vehicle)
    sensor = entities.get("ev_second_departure_days")
    assert sensor is not None
    assert sensor.native_value == "None"


async def test_departure_days_sensor_not_created_when_no_departure_data(
    setup_sensors,
) -> None:
    """Sensor is omitted on vehicles that report no departure schedule properties."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.engine_type = ENGINE_TYPES.EV
    vehicle.ev_first_departure_enabled = None
    vehicle.ev_first_departure_days = None
    vehicle.ev_first_departure_time = None

    entities = await setup_sensors(vehicle)
    assert "ev_first_departure_days" not in entities
