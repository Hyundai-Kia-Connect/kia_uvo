"""Tests for the charging-connector lock state sensor."""

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import CHARGING_CONNECTOR_LOCK_STATE
import pytest


@pytest.fixture
def lock_entity(setup_sensors):
    async def _entity(lock_state):
        vehicle = Vehicle(id="v1", name="test", model="test")
        vehicle.ev_connector_lock_state = lock_state
        return (await setup_sensors(vehicle)).get("ev_connector_lock_state")

    return _entity


async def test_missing_block_creates_no_entity(lock_entity) -> None:
    """Cars without the ChargingConnector block have no sensor."""
    assert await lock_entity(None) is None


async def test_each_state_maps_to_lowercased_name(lock_entity) -> None:
    """The sensor state is the enum's lowercase name."""
    cases = {
        CHARGING_CONNECTOR_LOCK_STATE.IDLE: "idle",
        CHARGING_CONNECTOR_LOCK_STATE.UNLOCKED: "unlocked",
        CHARGING_CONNECTOR_LOCK_STATE.LOCKED: "locked",
        CHARGING_CONNECTOR_LOCK_STATE.RELEASING: "releasing",
        CHARGING_CONNECTOR_LOCK_STATE.LOCKING: "locking",
        CHARGING_CONNECTOR_LOCK_STATE.RELEASED: "released",
    }
    for lock_state, expected in cases.items():
        entity = await lock_entity(lock_state)
        assert entity is not None
        assert entity.native_value == expected
