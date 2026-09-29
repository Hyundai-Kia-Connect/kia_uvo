"""Tests for the day-trip poll loop and DayTripInfoEntity.

The coordinator loop runs against the REAL library region implementations
(EU for a supported vehicle, CA for a region without the endpoint), with only
the HTTP call patched, so these tests pin the library contract: an empty day
leaves ``day_trip_info`` None without raising, and a region without the
endpoint raises NotImplementedError.
"""

import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.util import dt as dt_util
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.KiaUvoApiCA import KiaUvoApiCA
from hyundai_kia_connect_api.KiaUvoApiEU import KiaUvoApiEU
from hyundai_kia_connect_api.Vehicle import DayTripInfo, TripInfo

from custom_components.kia_uvo.coordinator import (
    HyundaiKiaConnectDataUpdateCoordinator,
)
from custom_components.kia_uvo.sensor import DayTripInfoEntity

TODAY = datetime.datetime(2026, 9, 29, 12, 0, 0)
YESTERDAY_STR = "20260928"
TODAY_STR = "20260929"


@pytest.fixture(autouse=True)
def _frozen_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dt_util, "now", lambda *_: TODAY)


def _eu_api(day_trip_list: list[dict[str, Any]] | Exception) -> KiaUvoApiEU:
    """Real EU implementation with the tripinfo HTTP call replaced."""
    api = KiaUvoApiEU(region=1, brand=2, language="en")

    def _get_trip_info(*_: Any) -> dict[str, Any]:
        if isinstance(day_trip_list, Exception):
            raise day_trip_list
        return {"resMsg": {"dayTripList": day_trip_list}}

    api._get_trip_info = _get_trip_info  # type: ignore[method-assign]
    return api


def _coordinator(api: Any, vehicle: Vehicle) -> Any:
    """Just enough coordinator for _async_update_day_trip_info."""

    async def _executor(func: Any, *args: Any) -> Any:
        return func(*args)

    return SimpleNamespace(
        day_trip_unsupported=set(),
        hass=SimpleNamespace(async_add_executor_job=_executor),
        vehicle_manager=SimpleNamespace(
            vehicles={vehicle.id: vehicle},
            update_day_trip_info=lambda vid, day: api.update_day_trip_info(
                None, vehicle, day
            ),
        ),
    )


async def _poll(coordinator: Any) -> None:
    await HyundaiKiaConnectDataUpdateCoordinator._async_update_day_trip_info(
        coordinator
    )


def _day(yyyymmdd: str, trips: int) -> DayTripInfo:
    return DayTripInfo(
        yyyymmdd=yyyymmdd,
        summary=TripInfo(drive_time=10 * trips),
        trip_list=[TripInfo(hhmmss=f"0{i}0000", drive_time=10) for i in range(trips)],
    )


def _payload(trips: int) -> list[dict[str, Any]]:
    trip = {
        "tripDrvTime": 10,
        "tripIdleTime": 1,
        "tripDist": 5,
        "tripAvgSpeed": 30,
        "tripMaxSpeed": 50,
    }
    return [
        {
            **trip,
            "tripList": [{**trip, "tripTime": f"0{i}0000"} for i in range(trips)],
        }
    ]


def _entity(vehicle: Vehicle, unsupported: set[str] | None = None) -> Any:
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.day_trip_unsupported = unsupported or set()
    return DayTripInfoEntity(coordinator, vehicle)


async def test_supported_vehicle_without_trips_stays_supported() -> None:
    """An empty day is not an unsupported endpoint; the sensor shows 0."""
    vehicle = Vehicle(id="v1")
    coordinator = _coordinator(_eu_api([]), vehicle)

    await _poll(coordinator)

    assert coordinator.day_trip_unsupported == set()
    assert vehicle.day_trip_info is None
    entity = _entity(vehicle, coordinator.day_trip_unsupported)
    assert entity.available
    assert entity.native_value == 0
    assert entity.extra_state_attributes == {
        "date": "2026-09-29",
        "summary": None,
        "trip_list": [],
    }


async def test_supported_vehicle_with_trips() -> None:
    vehicle = Vehicle(id="v1")
    coordinator = _coordinator(_eu_api(_payload(2)), vehicle)

    await _poll(coordinator)

    entity = _entity(vehicle, coordinator.day_trip_unsupported)
    assert entity.native_value == 2
    attrs = entity.extra_state_attributes
    assert attrs["date"] == "2026-09-29"
    assert attrs["trip_list"][0]["start_time"] == "2026-09-29T01:00:00"
    assert attrs["trip_list"][0]["end_time"] == "2026-09-29T01:11:00"


async def test_region_without_endpoint_is_unavailable_and_not_polled() -> None:
    vehicle = Vehicle(id="v1")
    api = KiaUvoApiCA(region=2, brand=2, language="en")
    coordinator = _coordinator(api, vehicle)

    await _poll(coordinator)

    assert coordinator.day_trip_unsupported == {"v1"}
    assert not _entity(vehicle, coordinator.day_trip_unsupported).available

    coordinator.vehicle_manager.update_day_trip_info = MagicMock()
    await _poll(coordinator)
    coordinator.vehicle_manager.update_day_trip_info.assert_not_called()


async def test_failed_fetch_keeps_todays_trips() -> None:
    """The library clears day_trip_info before a request that then fails."""
    vehicle = Vehicle(id="v1")
    vehicle.day_trip_info = _day(TODAY_STR, 3)
    coordinator = _coordinator(_eu_api(RuntimeError("timeout")), vehicle)

    await _poll(coordinator)

    assert coordinator.day_trip_unsupported == set()
    assert _entity(vehicle).native_value == 3


async def test_rollover_drops_yesterdays_trips_when_fetch_fails() -> None:
    vehicle = Vehicle(id="v1")
    vehicle.day_trip_info = _day(YESTERDAY_STR, 3)
    coordinator = _coordinator(_eu_api(RuntimeError("timeout")), vehicle)

    await _poll(coordinator)

    assert vehicle.day_trip_info is None
    assert _entity(vehicle).native_value == 0


async def test_sensor_ignores_yesterdays_data_before_first_poll() -> None:
    """Between midnight and the next poll the entity must not show yesterday."""
    vehicle = Vehicle(id="v1")
    vehicle.day_trip_info = _day(YESTERDAY_STR, 3)

    entity = _entity(vehicle)

    assert entity.native_value == 0
    assert entity.extra_state_attributes["date"] == "2026-09-29"
    assert entity.extra_state_attributes["trip_list"] == []
