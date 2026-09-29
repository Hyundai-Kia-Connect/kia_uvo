"""Tests for transient EV charging-power sensor creation."""

from unittest.mock import MagicMock

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES

from custom_components.kia_uvo import sensor as sensor_platform
from custom_components.kia_uvo.const import DOMAIN


async def _charging_power_entity(engine_type: ENGINE_TYPES | None, value: float | None):
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.engine_type = engine_type
    vehicle.ev_charging_power = value

    coordinator = MagicMock()
    coordinator.vehicle_manager.vehicles = {"v1": vehicle}
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.unique_id = "uid"
    hass.data = {DOMAIN: {"uid": coordinator}}
    created = []

    await sensor_platform.async_setup_entry(hass, config_entry, created.extend)

    return next(
        (
            entity
            for entity in created
            if getattr(entity, "entity_description", None) is not None
            and entity.entity_description.key == "ev_charging_power"
        ),
        None,
    )


async def test_ev_creates_charging_power_sensor_while_unplugged() -> None:
    """An unplugged EV still needs an entity for later charging updates."""
    entity = await _charging_power_entity(ENGINE_TYPES.EV, None)
    assert entity is not None
    assert entity.native_value is None


async def test_phev_creates_charging_power_sensor_while_unplugged() -> None:
    """An unplugged PHEV also retains the transient sensor."""
    assert await _charging_power_entity(ENGINE_TYPES.PHEV, None) is not None


async def test_ice_does_not_create_empty_charging_power_sensor() -> None:
    """ICE vehicles should not gain an unsupported charging-power entity."""
    assert await _charging_power_entity(ENGINE_TYPES.ICE, None) is None


async def test_reported_power_creates_sensor_when_engine_type_is_unknown() -> None:
    """Preserve discovery for backends that report power without engine type."""
    entity = await _charging_power_entity(None, 7.2)
    assert entity is not None
    assert entity.native_value == 7.2
