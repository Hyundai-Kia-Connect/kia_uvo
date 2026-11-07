"""Cabin PM2.5 sensor, vehicle detail attributes and the device model name.

Values follow a Kia India Seltos GT Line in Pewter Olive (codes GL / EWE).
"""

import datetime as dt
from zoneinfo import ZoneInfo

from conftest import make_coordinator, make_hass
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo import sensor as sensor_platform
from custom_components.kia_uvo.entity import HyundaiKiaConnectEntity

INDIA, EUROPE = 6, 1


def _seltos() -> Vehicle:
    vehicle = Vehicle(id="v1", name="SELTOS", model="SELTOS", VIN="VIN123")
    vehicle.year = 2025
    vehicle.trim_code = "GL"
    vehicle.exterior_color_code = "EWE"
    vehicle.interior_color_code = "WK"
    return vehicle


async def _sensors(vehicle: Vehicle, region: int = INDIA) -> dict:
    coordinator = make_coordinator(vehicle)
    coordinator.vehicle_manager.region = region
    coordinator.trip_stats_vehicle_ids = set()
    hass, config_entry = make_hass(coordinator)
    created: list = []
    await sensor_platform.async_setup_entry(hass, config_entry, created.extend)
    return {
        e.entity_description.key: e
        for e in created
        if getattr(e, "entity_description", None) is not None
    }


async def test_cabin_pm25_sensor_and_band():
    vehicle = _seltos()
    assert "cabin_pm25" not in await _sensors(vehicle)  # not reported

    vehicle.cabin_pm25 = 24
    vehicle.cabin_air_quality_level = 2
    vehicle.cabin_air_quality_measured_at = dt.datetime(
        2026, 10, 17, 21, 58, 20, tzinfo=ZoneInfo("Asia/Kolkata")
    )
    sensor = (await _sensors(vehicle))["cabin_pm25"]

    assert sensor.native_value == 24
    assert sensor.native_unit_of_measurement == "µg/m³"
    assert sensor.extra_state_attributes == {
        "level": 2,
        "colour": "green",
        "measured_at": vehicle.cabin_air_quality_measured_at,
    }


async def test_vin_sensor_lists_details_by_name_where_known():
    sensor = (await _sensors(_seltos()))["VIN"]
    assert sensor.extra_state_attributes == {
        "model_year": 2025,
        "trim": "GT Line",
        "exterior_color": "Pewter Olive",
        "interior_color_code": "WK",
    }


async def test_trim_code_only_named_for_its_region():
    sensor = (await _sensors(_seltos(), region=EUROPE))["VIN"]
    assert sensor.extra_state_attributes["trim"] == "GL"  # GL is its own trim elsewhere


async def test_unknown_codes_shown_raw_and_missing_ones_omitted():
    vehicle = Vehicle(id="v1", name="EV", model="EV6", VIN="VIN9")
    vehicle.exterior_color_code = "ZZZ"
    sensor = (await _sensors(vehicle))["VIN"]
    assert sensor.extra_state_attributes == {"exterior_color": "ZZZ"}


def _model_name(vehicle: Vehicle, region: int) -> str | None:
    coordinator = make_coordinator(vehicle)
    coordinator.vehicle_manager.region = region
    coordinator.vehicle_manager.brand = 1
    return HyundaiKiaConnectEntity(coordinator, vehicle).device_info["model"]


def test_device_model_includes_trim_and_year():
    assert _model_name(_seltos(), INDIA) == "SELTOS GT Line (2025)"
    assert _model_name(_seltos(), EUROPE) == "SELTOS (2025)"
    plain = Vehicle(id="v2", name="X", model="SPORTAGE")
    assert _model_name(plain, INDIA) == "SPORTAGE"
