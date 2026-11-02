"""Tests for EV State of Health sensor creation (kia_uvo #1935)."""

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES
import pytest


@pytest.fixture
def soh_entity(setup_sensors):
    async def _entity(value: float | None, engine_type: ENGINE_TYPES | None):
        vehicle = Vehicle(id="v1", name="test", model="test")
        vehicle.engine_type = engine_type
        vehicle.ev_battery_soh_percentage = value
        return (await setup_sensors(vehicle)).get("ev_battery_soh_percentage")

    return _entity


async def test_ev_creates_entity_without_a_reading(soh_entity) -> None:
    """The entity exists even while SOH stays filtered (e.g. 255 sentinel)."""
    entity = await soh_entity(None, ENGINE_TYPES.EV)
    assert entity is not None
    assert entity.native_value is None


async def test_phev_creates_entity_without_a_reading(soh_entity) -> None:
    """A PHEV also keeps the entity while no reading exists."""
    assert await soh_entity(None, ENGINE_TYPES.PHEV) is not None


async def test_creates_entity_with_a_reading(soh_entity) -> None:
    """A real SOH reading is reported by the same entity."""
    entity = await soh_entity(99, ENGINE_TYPES.EV)
    assert entity is not None
    assert entity.native_value == 99


async def test_ice_does_not_create_the_entity(soh_entity) -> None:
    """ICE vehicles have no SOH reading and gain no empty entity."""
    assert await soh_entity(None, ENGINE_TYPES.ICE) is None
