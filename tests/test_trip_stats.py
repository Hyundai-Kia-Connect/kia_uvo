"""Trip statistics: helpers, coordinator refresh and sensor entities.

Shapes follow a live Kia India Seltos: trip lists are newest-first, times
are in Asia/Kolkata, distances in km, durations in minutes.
"""

import datetime as dt
from functools import partial
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from conftest import make_coordinator, make_hass
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.Vehicle import (
    DayTripCounts,
    DayTripInfo,
    MonthTripInfo,
    TripInfo,
)

from custom_components.kia_uvo import sensor as sensor_platform
from custom_components.kia_uvo import trip_stats
from custom_components.kia_uvo.coordinator import (
    HyundaiKiaConnectDataUpdateCoordinator as Coordinator,
)

IST = ZoneInfo("Asia/Kolkata")


def _month(yyyymm: str, days: dict[str, int], distance: float = 100) -> MonthTripInfo:
    return MonthTripInfo(
        yyyymm=yyyymm,
        summary=TripInfo(
            drive_time=300,
            idle_time=40,
            distance=distance,
            avg_speed=29.5,
            max_speed=131,
        ),
        day_list=[DayTripCounts(yyyymmdd=d, trip_count=n) for d, n in days.items()],
    )


def _day(yyyymmdd: str) -> DayTripInfo:
    return DayTripInfo(
        yyyymmdd=yyyymmdd,
        summary=TripInfo(
            drive_time=79, idle_time=24, distance=22, avg_speed=16.7, max_speed=67
        ),
        trip_list=[
            TripInfo(
                hhmmss="201503",
                end_hhmmss="202457",
                drive_time=5,
                idle_time=3,
                distance=1,
                avg_speed=14,
                max_speed=45,
                hard_braking_count=2,
                rapid_acceleration_count=1,
                excessive_speed_count=0,
            ),
            TripInfo(hhmmss="081707", end_hhmmss="084539", distance=21),
        ],
    )


def _vehicle(month=None, day=None) -> Vehicle:
    vehicle = Vehicle(id="v1", name="SELTOS", model="SELTOS")
    vehicle.month_trip_info = month
    vehicle.day_trip_info = day
    return vehicle


# --- helpers -------------------------------------------------------------


def test_region_gating():
    assert trip_stats.region_supports_trip_stats(6)  # India
    assert not trip_stats.region_supports_trip_stats(1)  # Europe
    assert not trip_stats.region_supports_trip_stats(None)


def test_today_values_only_for_today():
    vehicle = _vehicle(_month("202610", {"20261017": 3}), _day("20261017"))
    assert trip_stats.today_summary(vehicle, "20261017").distance == 22
    assert trip_stats.today_trip_count(vehicle, "20261017") == 3
    assert trip_stats.today_summary(vehicle, "20261018") is None
    assert trip_stats.today_trip_count(vehicle, "20261018") == 0


def test_last_trip_is_newest_and_times_are_local():
    vehicle = _vehicle(day=_day("20261017"))
    assert trip_stats.last_trip(vehicle).distance == 1
    assert trip_stats.last_trip_start(vehicle, IST) == dt.datetime(
        2026, 10, 17, 20, 15, 3, tzinfo=IST
    )
    assert trip_stats.last_trip_end(vehicle, IST) == dt.datetime(
        2026, 10, 17, 20, 24, 57, tzinfo=IST
    )


def test_last_trip_end_past_midnight_rolls_to_next_day():
    day = _day("20261017")
    day.trip_list = [TripInfo(hhmmss="235000", end_hhmmss="001500")]
    vehicle = _vehicle(day=day)
    assert trip_stats.last_trip_end(vehicle, IST) == dt.datetime(
        2026, 10, 18, 0, 15, tzinfo=IST
    )


def test_latest_trip_day_and_month_count():
    vehicle = _vehicle(_month("202610", {"20261003": 6, "20261017": 3, "20261005": 9}))
    assert trip_stats.latest_trip_day(vehicle) == "20261017"
    assert trip_stats.month_trip_count(vehicle) == 18
    assert trip_stats.latest_trip_day(_vehicle()) is None


# --- coordinator refresh --------------------------------------------------


class FakeManager:
    """VehicleManager stand-in serving scripted trip history."""

    def __init__(self, vehicle: Vehicle, months: dict[str, MonthTripInfo | None]):
        self.vehicles = {vehicle.id: vehicle}
        self.months = months
        self.calls: list[tuple[str, str]] = []
        self.fail = False

    def update_month_trip_info(self, vehicle_id: str, yyyymm: str) -> None:
        self.calls.append(("month", yyyymm))
        if self.fail:
            raise RuntimeError("API down")
        self.vehicles[vehicle_id].month_trip_info = self.months.get(yyyymm)

    def update_day_trip_info(self, vehicle_id: str, yyyymmdd: str) -> None:
        self.calls.append(("day", yyyymmdd))
        self.vehicles[vehicle_id].day_trip_info = _day(yyyymmdd)


def _fake_coordinator(manager: FakeManager, now: dt.datetime) -> SimpleNamespace:
    fake = SimpleNamespace(
        vehicle_manager=manager,
        trip_timezone=IST,
        trip_stats_vehicle_ids=set(),
        trip_stats_ok={},
        _trip_signatures={},
    )
    fake._latest_trip_day_last_month = partial(
        Coordinator._latest_trip_day_last_month, fake
    )
    fake.update = partial(Coordinator.update_trip_stats, fake)
    return fake


@pytest.fixture
def frozen_now(monkeypatch):
    """Freeze the coordinator's clock at 2026-10-20 12:00 IST."""
    now = dt.datetime(2026, 10, 20, 12, 0, tzinfo=IST)

    class FrozenDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now

    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.dt.datetime", FrozenDatetime
    )
    return now


def test_day_trips_refetched_only_after_new_trip(frozen_now):
    vehicle = _vehicle()
    months = {"202610": _month("202610", {"20261017": 3})}
    manager = FakeManager(vehicle, months)
    coordinator = _fake_coordinator(manager, frozen_now)

    coordinator.update()
    coordinator.update()  # nothing changed: month only
    months["202610"] = _month("202610", {"20261017": 3, "20261020": 1}, distance=110)
    coordinator.update()  # new trip today

    assert manager.calls == [
        ("month", "202610"),
        ("day", "20261017"),
        ("month", "202610"),
        ("month", "202610"),
        ("day", "20261020"),
    ]
    assert vehicle.day_trip_info.yyyymmdd == "20261020"
    assert coordinator.trip_stats_vehicle_ids == {"v1"}
    assert coordinator.trip_stats_ok == {"v1": True}


def test_empty_month_uses_last_months_trip_and_keeps_current_month(frozen_now):
    vehicle = _vehicle()
    manager = FakeManager(
        vehicle, {"202610": None, "202609": _month("202609", {"20260928": 2})}
    )
    coordinator = _fake_coordinator(manager, frozen_now)

    coordinator.update()

    assert manager.calls == [
        ("month", "202610"),
        ("month", "202609"),
        ("day", "20260928"),
    ]
    assert vehicle.month_trip_info is None  # still the current (empty) month
    assert vehicle.day_trip_info.yyyymmdd == "20260928"


def test_failure_is_contained_and_marks_unavailable(frozen_now):
    vehicle = _vehicle()
    manager = FakeManager(vehicle, {})
    manager.fail = True
    coordinator = _fake_coordinator(manager, frozen_now)

    coordinator.update()  # must not raise

    assert coordinator.trip_stats_ok == {"v1": False}
    assert coordinator.trip_stats_vehicle_ids == set()


# --- sensor entities -------------------------------------------------------


async def _setup_trip_sensors(vehicle: Vehicle, with_trips: bool, ok: bool = True):
    coordinator = make_coordinator(vehicle)
    coordinator.trip_stats_vehicle_ids = {vehicle.id} if with_trips else set()
    coordinator.trip_stats_ok = {vehicle.id: ok}
    coordinator.trip_timezone = IST
    hass, config_entry = make_hass(coordinator)
    created: list = []
    await sensor_platform.async_setup_entry(hass, config_entry, created.extend)
    return {
        e.entity_description.key: e
        for e in created
        if isinstance(e, sensor_platform.HyundaiKiaTripSensor)
    }


async def test_trip_sensors_only_created_for_trip_vehicles():
    vehicle = _vehicle()
    assert await _setup_trip_sensors(vehicle, with_trips=False) == {}
    sensors = await _setup_trip_sensors(vehicle, with_trips=True)
    assert set(sensors) == {d.key for d in sensor_platform.TRIP_SENSOR_DESCRIPTIONS}


async def test_trip_sensor_values(monkeypatch):
    class FrozenDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 10, 17, 21, 0, tzinfo=IST).astimezone(tz)

    monkeypatch.setattr(sensor_platform, "datetime", FrozenDatetime)
    vehicle = _vehicle(
        _month("202610", {"20261005": 9, "20261017": 3}), _day("20261017")
    )
    sensors = await _setup_trip_sensors(vehicle, with_trips=True)
    values = {k: s.native_value for k, s in sensors.items()}

    assert values["trip_today_distance"] == 22
    assert values["trip_today_drive_time"] == 79
    assert values["trip_today_count"] == 3
    assert values["trip_month_distance"] == 100
    assert values["trip_month_count"] == 12
    assert values["trip_month_max_speed"] == 131
    assert values["last_trip_distance"] == 1
    assert values["last_trip_hard_braking"] == 2
    assert values["last_trip_rapid_acceleration"] == 1
    assert values["last_trip_speeding"] == 0
    assert values["last_trip_start"] == dt.datetime(2026, 10, 17, 20, 15, 3, tzinfo=IST)


async def test_today_sensors_zero_on_a_day_without_trips(monkeypatch):
    class FrozenDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 10, 18, 9, 0, tzinfo=IST).astimezone(tz)

    monkeypatch.setattr(sensor_platform, "datetime", FrozenDatetime)
    vehicle = _vehicle(_month("202610", {"20261017": 3}), _day("20261017"))
    sensors = await _setup_trip_sensors(vehicle, with_trips=True)

    assert sensors["trip_today_distance"].native_value == 0
    assert sensors["trip_today_count"].native_value == 0
    assert sensors["last_trip_distance"].native_value == 1  # still yesterday's


async def test_trip_sensors_unavailable_after_failed_refresh():
    vehicle = _vehicle(_month("202610", {"20261017": 3}))
    sensors = await _setup_trip_sensors(vehicle, with_trips=True, ok=False)
    sensors["trip_month_distance"].coordinator.last_update_success = True
    assert sensors["trip_month_distance"].available is False


# --- quick wins -------------------------------------------------------------


async def test_hazard_binary_sensor_created_when_reported():
    from custom_components.kia_uvo import binary_sensor as binary_platform

    async def keys(vehicle):
        hass, config_entry = make_hass(make_coordinator(vehicle))
        created: list = []
        await binary_platform.async_setup_entry(hass, config_entry, created.extend)
        return {e.entity_description.key for e in created}

    vehicle = _vehicle()
    assert "hazard_lights_on" not in await keys(vehicle)
    vehicle.hazard_lights_on = False
    assert "hazard_lights_on" in await keys(vehicle)


def test_device_tracker_motion_attributes():
    from custom_components.kia_uvo.device_tracker import HyundaiKiaConnectTracker

    vehicle = _vehicle()
    vehicle.location_speed = 23
    vehicle.location_heading = 277
    tracker = HyundaiKiaConnectTracker(MagicMock(), vehicle)

    assert tracker.extra_state_attributes == {"speed": 23, "heading": 277}
