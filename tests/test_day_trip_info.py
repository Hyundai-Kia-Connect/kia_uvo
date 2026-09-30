"""Tests for the day-trip poll loop and DayTripInfoEntity.

The coordinator loop runs against the REAL library region implementations
(EU for a supported vehicle, CA for a region without the endpoint), with only
the HTTP call patched, so these tests pin the library contract: an empty day
leaves ``day_trip_info`` None without raising, and a region without the
endpoint raises NotImplementedError.

The clock is frozen at noon, so every poll also runs the once-a-day catch-up
fetch of the previous day; the fake API returns no trips for days it is not
given.
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

Payload = list[dict[str, Any]] | Exception


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Frozen dt_util.now(); tests move it by setting ``clock.now``."""
    frozen = SimpleNamespace(now=TODAY)
    monkeypatch.setattr(dt_util, "now", lambda *_: frozen.now)
    return frozen


class _EuApi(KiaUvoApiEU):
    """Real EU implementation with the tripinfo HTTP call replaced."""

    def __init__(self, days: dict[str, Payload]) -> None:
        super().__init__(region=1, brand=2, language="en")
        self.days = days
        self.requested: list[str] = []

    def _get_trip_info(self, _token: Any, _vehicle: Any, day: str, _kind: int) -> Any:
        self.requested.append(day)
        payload = self.days.get(day, [])
        if isinstance(payload, Exception):
            raise payload
        return {"resMsg": {"dayTripList": payload}}


def _eu_api(today: Payload) -> _EuApi:
    return _EuApi({TODAY_STR: today})


def _coordinator(api: Any, vehicle: Vehicle) -> Any:
    """Real coordinator, skipping __init__ (no HA or VehicleManager setup)."""

    async def _executor(func: Any, *args: Any) -> Any:
        return func(*args)

    coordinator = object.__new__(HyundaiKiaConnectDataUpdateCoordinator)
    coordinator.day_trip_unsupported = set()
    coordinator._day_trip_shown = {}
    coordinator._day_trip_caught_up = {}
    coordinator.day_trip_catch_up = {}
    coordinator.last_update_success = True
    coordinator.hass = SimpleNamespace(async_add_executor_job=_executor)
    coordinator.vehicle_manager = SimpleNamespace(
        vehicles={vehicle.id: vehicle},
        update_day_trip_info=lambda vid, day: api.update_day_trip_info(
            None, vehicle, day
        ),
    )
    return coordinator


async def _poll(coordinator: Any) -> None:
    await coordinator._async_update_day_trip_info()


def _day(yyyymmdd: str, trips: int) -> DayTripInfo:
    return DayTripInfo(
        yyyymmdd=yyyymmdd,
        summary=TripInfo(drive_time=10 * trips),
        trip_list=[TripInfo(hhmmss=f"0{i}0000", drive_time=10) for i in range(trips)],
    )


def _payload(trips: int | list[str]) -> list[dict[str, Any]]:
    """Day payload with ``trips`` trips, or trips at the given HHMMSS times."""
    trip = {
        "tripDrvTime": 10,
        "tripIdleTime": 1,
        "tripDist": 5,
        "tripAvgSpeed": 30,
        "tripMaxSpeed": 50,
    }
    times = trips if isinstance(trips, list) else [f"0{i}0000" for i in range(trips)]
    return [{**trip, "tripList": [{**trip, "tripTime": t} for t in times]}]


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


async def test_trip_crossing_midnight_is_written_as_catch_up_state(
    clock: SimpleNamespace,
) -> None:
    """A trip ending after midnight appears once, dated on its start day."""
    vehicle = Vehicle(id="v1")
    api = _EuApi({YESTERDAY_STR: _payload(["120000"])})
    coordinator = _coordinator(api, vehicle)
    entity = DayTripInfoEntity(coordinator, vehicle)
    written: list[tuple[Any, dict[str, Any]]] = []
    entity.async_write_ha_state = lambda: written.append(
        (entity.native_value, entity.extra_state_attributes)
    )

    # 23:50: only the noon trip is uploaded; the 23:52 trip is still driving.
    clock.now = datetime.datetime(2026, 9, 28, 23, 50)
    await _poll(coordinator)
    assert entity.native_value == 1

    # The 23:52 trip ends at 00:21 and is booked on its start day.
    api.days[YESTERDAY_STR] = _payload(["120000", "235258"])

    # Before the catch-up hour only today is fetched.
    clock.now = datetime.datetime(2026, 9, 29, 0, 30)
    api.requested.clear()
    await _poll(coordinator)
    assert api.requested == [TODAY_STR]
    assert coordinator.day_trip_catch_up == {}

    clock.now = datetime.datetime(2026, 9, 29, 4, 10)
    api.requested.clear()
    await _poll(coordinator)
    assert api.requested == [YESTERDAY_STR, TODAY_STR]
    written.clear()
    entity._handle_coordinator_update()

    (catch_up_value, catch_up_attrs), (today_value, today_attrs) = written
    assert catch_up_value == 2
    assert catch_up_attrs["date"] == "2026-09-28"
    assert catch_up_attrs["trip_list"][0]["start_time"] == "2026-09-28T23:52:58"
    assert today_value == 0
    assert today_attrs["date"] == "2026-09-29"
    assert today_attrs["trip_list"] == []

    # One catch-up per day: later polls fetch only today.
    clock.now = datetime.datetime(2026, 9, 29, 4, 40)
    api.requested.clear()
    await _poll(coordinator)
    assert api.requested == [TODAY_STR]
    assert coordinator.day_trip_catch_up == {}


async def test_catch_up_without_new_trips_writes_no_extra_state(
    clock: SimpleNamespace,
) -> None:
    vehicle = Vehicle(id="v1")
    api = _EuApi({YESTERDAY_STR: _payload(1)})
    coordinator = _coordinator(api, vehicle)

    clock.now = datetime.datetime(2026, 9, 28, 23, 50)
    await _poll(coordinator)
    clock.now = datetime.datetime(2026, 9, 29, 4, 10)
    await _poll(coordinator)

    assert api.requested[-2:] == [YESTERDAY_STR, TODAY_STR]
    assert coordinator.day_trip_catch_up == {}


async def test_failed_catch_up_is_not_retried_and_keeps_today() -> None:
    vehicle = Vehicle(id="v1")
    api = _EuApi({YESTERDAY_STR: RuntimeError("timeout"), TODAY_STR: _payload(2)})
    coordinator = _coordinator(api, vehicle)

    await _poll(coordinator)
    await _poll(coordinator)

    assert api.requested == [YESTERDAY_STR, TODAY_STR, TODAY_STR]
    assert coordinator.day_trip_unsupported == set()
    assert coordinator.day_trip_catch_up == {}
    assert _entity(vehicle).native_value == 2
