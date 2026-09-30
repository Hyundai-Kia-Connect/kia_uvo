"""Tests for transient EV target-charge-range sensor creation."""

import pytest
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES

_TARGET_RANGE_KEYS = ("_ev_target_range_charge_AC", "_ev_target_range_charge_DC")


@pytest.fixture
def target_range_entities(setup_sensors):
    async def _entities(
        engine_type: ENGINE_TYPES | None, values: dict[str, float | None]
    ) -> dict:
        """Return the created target-range entities (AC + DC), keyed by key."""
        vehicle = Vehicle(id="v1", name="test", model="test")
        vehicle.engine_type = engine_type
        for key, value in values.items():
            # sensor.py reads the private dataclass field directly via getattr.
            setattr(vehicle, key, value)
        entities = await setup_sensors(vehicle)
        return {k: e for k, e in entities.items() if k in _TARGET_RANGE_KEYS}

    return _entities


async def test_ev_creates_target_range_sensors_when_value_absent(
    target_range_entities,
) -> None:
    """An asleep EV still needs entities for later target-range polls. See #1842."""
    entities = await target_range_entities(
        ENGINE_TYPES.EV, dict.fromkeys(_TARGET_RANGE_KEYS)
    )
    assert set(entities) == set(_TARGET_RANGE_KEYS)
    assert all(e.native_value is None for e in entities.values())


async def test_phev_creates_target_range_sensors_when_value_absent(
    target_range_entities,
) -> None:
    """A PHEV also retains the transient target-range sensors."""
    entities = await target_range_entities(
        ENGINE_TYPES.PHEV, dict.fromkeys(_TARGET_RANGE_KEYS)
    )
    assert set(entities) == set(_TARGET_RANGE_KEYS)


async def test_ice_does_not_create_target_range_sensors(target_range_entities) -> None:
    """ICE vehicles should not gain unsupported target-charge-range entities."""
    entities = await target_range_entities(
        ENGINE_TYPES.ICE, dict.fromkeys(_TARGET_RANGE_KEYS)
    )
    assert entities == {}


async def test_reported_range_creates_sensors_when_engine_type_is_unknown(
    target_range_entities,
) -> None:
    """Preserve discovery for backends that report target range without engine type."""
    values = {"_ev_target_range_charge_AC": 591, "_ev_target_range_charge_DC": 525}
    entities = await target_range_entities(None, values)
    assert entities["_ev_target_range_charge_AC"].native_value == 591
    assert entities["_ev_target_range_charge_DC"].native_value == 525
