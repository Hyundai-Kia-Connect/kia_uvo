"""Tests for transient EV charging-power sensor creation."""

import pytest
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES


@pytest.fixture
def charging_power_entity(setup_sensors):
    async def _entity(engine_type: ENGINE_TYPES | None, value: float | None):
        vehicle = Vehicle(id="v1", name="test", model="test")
        vehicle.engine_type = engine_type
        vehicle.ev_charging_power = value
        return (await setup_sensors(vehicle)).get("ev_charging_power")

    return _entity


async def test_ev_creates_charging_power_sensor_while_unplugged(
    charging_power_entity,
) -> None:
    """An unplugged EV still needs an entity for later charging updates."""
    entity = await charging_power_entity(ENGINE_TYPES.EV, None)
    assert entity is not None
    assert entity.native_value is None


async def test_phev_creates_charging_power_sensor_while_unplugged(
    charging_power_entity,
) -> None:
    """An unplugged PHEV also retains the transient sensor."""
    assert await charging_power_entity(ENGINE_TYPES.PHEV, None) is not None


async def test_ice_does_not_create_empty_charging_power_sensor(
    charging_power_entity,
) -> None:
    """ICE vehicles should not gain an unsupported charging-power entity."""
    assert await charging_power_entity(ENGINE_TYPES.ICE, None) is None


async def test_reported_power_creates_sensor_when_engine_type_is_unknown(
    charging_power_entity,
) -> None:
    """Preserve discovery for backends that report power without engine type."""
    entity = await charging_power_entity(None, 7.2)
    assert entity is not None
    assert entity.native_value == 7.2
