"""Tests for the EV plug binary sensor creation gate."""

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES
import pytest


@pytest.fixture
def plug_entity(setup_binary_sensors):
    async def _entity(engine_type: ENGINE_TYPES | None, value: bool | None):
        vehicle = Vehicle(id="v1", name="test", model="test")
        vehicle.engine_type = engine_type
        vehicle.ev_battery_is_plugged_in = value
        return (await setup_binary_sensors(vehicle)).get("ev_battery_is_plugged_in")

    return _entity


async def test_ev_gets_entity_while_unplugged(plug_entity) -> None:
    """An unplugged EV keeps the plug entity; the value reads unknown."""
    entity = await plug_entity(ENGINE_TYPES.EV, None)
    assert entity is not None
    assert entity.is_on is None


async def test_phev_gets_entity_while_unplugged(plug_entity) -> None:
    """An unplugged PHEV also retains the plug entity."""
    assert await plug_entity(ENGINE_TYPES.PHEV, None) is not None


async def test_ice_gets_no_entity(plug_entity) -> None:
    """ICE vehicles must not gain a plug entity."""
    assert await plug_entity(ENGINE_TYPES.ICE, None) is None


async def test_reported_value_keeps_creation_for_unknown_engine_type(
    plug_entity,
) -> None:
    """Preserve discovery for backends that report plug without engine type."""
    entity = await plug_entity(None, True)
    assert entity is not None
    assert entity.is_on is True
