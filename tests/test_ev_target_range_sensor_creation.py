"""Tests for transient EV target-charge-range sensor creation."""

from unittest.mock import MagicMock

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES

from custom_components.kia_uvo import sensor as sensor_platform
from custom_components.kia_uvo.const import DOMAIN

_TARGET_RANGE_KEYS = ("_ev_target_range_charge_AC", "_ev_target_range_charge_DC")


async def _target_range_entity(
    engine_type: ENGINE_TYPES | None,
    values: dict[str, float | None],
) -> list:
    """Return the created target-range entities (AC + DC) for the vehicle."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.engine_type = engine_type
    for key, value in values.items():
        # sensor.py reads the private dataclass field directly via getattr.
        setattr(vehicle, key, value)

    coordinator = MagicMock()
    coordinator.vehicle_manager.vehicles = {"v1": vehicle}
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.unique_id = "uid"
    hass.data = {DOMAIN: {"uid": coordinator}}
    created = []

    await sensor_platform.async_setup_entry(hass, config_entry, created.extend)

    return [
        e
        for e in created
        if getattr(e, "entity_description", None) is not None
        and e.entity_description.key in _TARGET_RANGE_KEYS
    ]


async def test_ev_creates_target_range_sensors_when_value_absent() -> None:
    """An asleep EV still needs entities for later target-range polls. See #1842."""
    entities = await _target_range_entity(
        ENGINE_TYPES.EV, {k: None for k in _TARGET_RANGE_KEYS}
    )
    keys = {e.entity_description.key for e in entities}
    assert keys == set(_TARGET_RANGE_KEYS)
    assert all(e.native_value is None for e in entities)


async def test_phev_creates_target_range_sensors_when_value_absent() -> None:
    """A PHEV also retains the transient target-range sensors."""
    entities = await _target_range_entity(
        ENGINE_TYPES.PHEV, {k: None for k in _TARGET_RANGE_KEYS}
    )
    assert {e.entity_description.key for e in entities} == set(_TARGET_RANGE_KEYS)


async def test_ice_does_not_create_target_range_sensors() -> None:
    """ICE vehicles should not gain unsupported target-charge-range entities."""
    assert (
        await _target_range_entity(
            ENGINE_TYPES.ICE, {k: None for k in _TARGET_RANGE_KEYS}
        )
        == []
    )


async def test_reported_range_creates_sensors_when_engine_type_is_unknown() -> None:
    """Preserve discovery for backends that report target range without engine type."""
    values = {"_ev_target_range_charge_AC": 591, "_ev_target_range_charge_DC": 525}
    entities = await _target_range_entity(None, values)
    by_key = {e.entity_description.key: e for e in entities}
    assert by_key["_ev_target_range_charge_AC"].native_value == 591
    assert by_key["_ev_target_range_charge_DC"].native_value == 525
