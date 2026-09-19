"""Tests for /drvhistory sensor creation gating (#1896).

Region ids are ints (config_flow stores CONF_REGION as an int index into
REGIONS) — the same shape production uses, so these tests would catch an
int-vs-string comparison regression.
"""

import datetime
from unittest.mock import AsyncMock, MagicMock

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES
from hyundai_kia_connect_api.Vehicle import DailyDrivingStats

from custom_components.kia_uvo import sensor as sensor_platform
from custom_components.kia_uvo.const import DOMAIN, REGIONS

_REGION_EU = 1
_REGION_CN = 4
_REGION_AU = 5
_REGION_IN = 6
_REGION_USA = 3

_DRVHISTORY_KEYS = (
    "total_power_consumed",
    "total_power_regenerated",
    "power_consumption_30d",
)
_DAILY_STATS_CLASSES = ("DailyDrivingStatsEntity", "TodaysDailyDrivingStatsEntity")


def _stats_entry(date: datetime.datetime) -> DailyDrivingStats:
    return DailyDrivingStats(
        date=date, total_consumed=100, regenerated_energy=10, distance=30.0
    )


async def _setup_entities(
    region_id: int,
    engine_type: ENGINE_TYPES | None,
    values: dict[str, float | None],
    daily_stats: list[DailyDrivingStats] | None,
) -> list:
    """Return the created /drvhistory entities for the vehicle."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.engine_type = engine_type
    for key, value in values.items():
        setattr(vehicle, key, value)
    vehicle.daily_stats = daily_stats

    coordinator = MagicMock()
    coordinator.vehicle_manager.vehicles = {"v1": vehicle}
    coordinator.vehicle_manager.region = region_id
    coordinator.async_supports_svm = AsyncMock(return_value=False)
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.unique_id = "uid"
    hass.data = {DOMAIN: {"uid": coordinator}}
    created: list = []

    await sensor_platform.async_setup_entry(hass, config_entry, created.extend)

    return [
        e
        for e in created
        if (
            getattr(e, "entity_description", None) is not None
            and e.entity_description.key in _DRVHISTORY_KEYS
        )
        or e.__class__.__name__ in _DAILY_STATS_CLASSES
    ]


def _keys_of(entities: list) -> set[str]:
    return {
        e.entity_description.key
        if getattr(e, "entity_description", None) is not None
        else e.__class__.__name__
        for e in entities
    }


async def test_eu_ev_creates_entities_without_data() -> None:
    """An EU EV with no /drvhistory data keeps its entities. See #1896."""
    entities = await _setup_entities(
        _REGION_EU, ENGINE_TYPES.EV, {k: None for k in _DRVHISTORY_KEYS}, None
    )
    grouped = {
        e: [x for x in entities if _keys_of([x]) == {e}] for e in _keys_of(entities)
    }
    assert _keys_of(entities) == set(_DRVHISTORY_KEYS) | set(_DAILY_STATS_CLASSES)
    assert all(grouped[key][0].native_value is None for key in _DRVHISTORY_KEYS)
    # No data -> `unknown`, not a misleading 0 days.
    daily = grouped["DailyDrivingStatsEntity"][0]
    assert daily.native_value is None
    assert daily.extra_state_attributes == {}
    # Today's entity always reports today's date, with zeroed attributes.
    todays = grouped["TodaysDailyDrivingStatsEntity"][0]
    assert todays.native_value == datetime.date.today().strftime("%Y-%m-%d")
    assert todays.extra_state_attributes["distance"] == 0


async def test_eu_phev_creates_entities_without_data() -> None:
    """A PHEV gets the same retention."""
    entities = await _setup_entities(
        _REGION_EU, ENGINE_TYPES.PHEV, {k: None for k in _DRVHISTORY_KEYS}, None
    )
    assert _keys_of(entities) == set(_DRVHISTORY_KEYS) | set(_DAILY_STATS_CLASSES)


async def test_eu_ev_reports_present_data() -> None:
    """Data present at setup still produces the populated entities."""
    stats = [_stats_entry(datetime.datetime(2026, 9, 16))]
    entities = await _setup_entities(
        _REGION_EU,
        ENGINE_TYPES.EV,
        {
            "total_power_consumed": 90_000.0,
            "total_power_regenerated": 1_000.0,
            "power_consumption_30d": 150.0,
        },
        stats,
    )
    grouped = {
        e: [x for x in entities if _keys_of([x]) == {e}] for e in _keys_of(entities)
    }
    assert grouped["total_power_consumed"][0].native_value == 90_000.0
    assert grouped["power_consumption_30d"][0].native_value == 150.0
    assert grouped["DailyDrivingStatsEntity"][0].native_value == 1
    # Stats are from 2026-09-16, not today.
    assert (
        grouped["TodaysDailyDrivingStatsEntity"][0].extra_state_attributes[
            "total_consumed"
        ]
        == 0
    )


async def test_india_ev_gets_all_entities_including_regenerated() -> None:
    """India's implementation parses regenPwr like the EU one."""
    entities = await _setup_entities(
        _REGION_IN, ENGINE_TYPES.EV, {k: None for k in _DRVHISTORY_KEYS}, None
    )
    assert _keys_of(entities) == set(_DRVHISTORY_KEYS) | set(_DAILY_STATS_CLASSES)


async def test_australia_ev_has_no_regenerated_sensor() -> None:
    """The AU impl (shared with NZ) never parses regenPwr."""
    entities = await _setup_entities(
        _REGION_AU, ENGINE_TYPES.EV, {k: None for k in _DRVHISTORY_KEYS}, None
    )
    assert _keys_of(entities) == (
        set(_DRVHISTORY_KEYS) - {"total_power_regenerated"}
    ) | set(_DAILY_STATS_CLASSES)


async def test_china_ev_has_no_regenerated_sensor() -> None:
    """The CN impl never parses regenPwr either."""
    entities = await _setup_entities(
        _REGION_CN, ENGINE_TYPES.EV, {k: None for k in _DRVHISTORY_KEYS}, None
    )
    assert _keys_of(entities) == (
        set(_DRVHISTORY_KEYS) - {"total_power_regenerated"}
    ) | set(_DAILY_STATS_CLASSES)


async def test_china_phev_gets_no_drvhistory_entities() -> None:
    """The CN impl only polls /drvhistory for BEV (mirrors the library)."""
    entities = await _setup_entities(
        _REGION_CN, ENGINE_TYPES.PHEV, {k: None for k in _DRVHISTORY_KEYS}, None
    )
    assert entities == []


async def test_usa_ev_gets_no_drvhistory_entities() -> None:
    """The USA impl never polls /drvhistory."""
    entities = await _setup_entities(
        _REGION_USA, ENGINE_TYPES.EV, {k: None for k in _DRVHISTORY_KEYS}, None
    )
    assert entities == []


async def test_eu_ice_gets_no_drvhistory_entities() -> None:
    """The library only polls /drvhistory for electrified vehicles."""
    entities = await _setup_entities(
        _REGION_EU, ENGINE_TYPES.ICE, {k: None for k in _DRVHISTORY_KEYS}, None
    )
    assert entities == []


async def test_region_ids_map_to_expected_region_names() -> None:
    """Guard the int region ids used across this test module."""
    assert REGIONS[_REGION_EU] == "Europe"
    assert REGIONS[_REGION_CN] == "China"
    assert REGIONS[_REGION_AU] == "Australia"
    assert REGIONS[_REGION_IN] == "India"
    assert REGIONS[_REGION_USA] == "USA"
