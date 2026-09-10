"""Regression tests for Bluelink subscription migrations (issue #1852)."""

from unittest.mock import MagicMock

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES

from custom_components.kia_uvo import sensor as sensor_platform
from custom_components.kia_uvo.const import DOMAIN
from custom_components.kia_uvo.entity import HyundaiKiaConnectEntity


def _vehicle(vehicle_id: str = "backend-id") -> Vehicle:
    vehicle = Vehicle(id=vehicle_id, name="Kona", model="Kona EV")
    vehicle.VIN = "KMH12345678901234"
    vehicle.engine_type = ENGINE_TYPES.EV
    return vehicle


def test_vin_keeps_device_identity_when_backend_id_changes() -> None:
    """A subscription migration must not make the same VIN a new device."""
    coordinator = MagicMock()
    coordinator.vehicle_manager.brand = 1
    coordinator.vehicle_manager.region = 1

    before = HyundaiKiaConnectEntity(coordinator, _vehicle("old-id")).device_info
    after = HyundaiKiaConnectEntity(coordinator, _vehicle("new-id")).device_info

    assert (DOMAIN, "vin:KMH12345678901234") in before["identifiers"]
    assert before["identifiers"] & after["identifiers"]


async def test_ev_telemetry_entities_survive_empty_setup_payload() -> None:
    """Transiently absent Bluelink values must not remove EV entities."""
    vehicle = _vehicle()
    vehicle._odometer = None
    vehicle.total_power_consumed = None
    vehicle.total_power_regenerated = None
    vehicle.power_consumption_30d = None
    vehicle.daily_stats = []

    coordinator = MagicMock()
    coordinator.vehicle_manager.vehicles = {vehicle.id: vehicle}
    hass = MagicMock()
    config_entry = MagicMock(unique_id="uid")
    hass.data = {DOMAIN: {"uid": coordinator}}
    created = []

    await sensor_platform.async_setup_entry(hass, config_entry, created.extend)

    description_keys = {
        entity.entity_description.key
        for entity in created
        if getattr(entity, "entity_description", None) is not None
    }
    assert {
        "_odometer",
        "total_power_consumed",
        "total_power_regenerated",
        "power_consumption_30d",
    } <= description_keys
    assert any(
        entity.unique_id == f"{DOMAIN}-daily-driving-stats-{vehicle.id}"
        for entity in created
    )
    assert any(
        entity.unique_id == f"{DOMAIN}-todays-daily-driving-stats-{vehicle.id}"
        for entity in created
    )
