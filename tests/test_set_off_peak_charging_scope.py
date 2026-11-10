"""set_off_peak_charging must not touch the departure/climate scope.

The library's "None = leave unchanged" fill turns an untouched climate scope
into "no /hvac request" on the flat CCS2 path (#2100); full-filling it
from cached state sent that request and turned departure 1 off on an EV6.
"""

from datetime import time
from unittest.mock import AsyncMock

from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo.const import OffPeakChargingMode
from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator


def _coordinator(vehicle: Vehicle):
    coordinator = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    coordinator.vehicle_manager = type(
        "VehicleManagerStub", (), {"vehicles": {vehicle.id: vehicle}}
    )()
    coordinator.async_schedule_charging_and_climate = AsyncMock()
    return coordinator


async def test_service_mode_time_sends_charge_scope_only():
    vehicle = Vehicle(
        id="v1",
        name="test",
        model="test",
        ev_first_departure_enabled=True,
        ev_first_departure_time=time(6, 50),
        ev_first_departure_climate_enabled=True,
        ev_schedule_charge_enabled=True,
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_off_peak_charging(
        "v1", mode=OffPeakChargingMode.TIME, start=time(11, 0), end=time(17, 0)
    )
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.first_departure is None
    assert options.second_departure is None
    assert options.climate_enabled is None
    assert options.temperature is None
    assert options.defrost is None
    assert options.charging_enabled is True
    assert options.off_peak_charge_only_enabled is True
    assert options.off_peak_start_time == time(11, 0)
    assert options.off_peak_end_time == time(17, 0)


async def test_mode_none_preserves_vehicle_mode_and_window():
    vehicle = Vehicle(
        id="v1",
        name="test",
        model="test",
        ev_schedule_charge_enabled=True,
        ev_off_peak_charge_only_enabled=False,
        ev_off_peak_start_time=time(22, 0),
        ev_off_peak_end_time=time(7, 0),
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_off_peak_charging("v1", start=time(5, 0))
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.charging_enabled is True
    assert options.off_peak_charge_only_enabled is False
    assert options.off_peak_start_time == time(5, 0)
    assert options.off_peak_end_time == time(7, 0)
    assert not coordinator.async_schedule_charging_and_climate.await_args.kwargs


async def test_mode_off_disables_charge_only():
    vehicle = Vehicle(
        id="v1", name="test", model="test", ev_off_peak_charge_only_enabled=True
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_off_peak_charging("v1", mode=OffPeakChargingMode.OFF)
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.charging_enabled is False
    assert options.off_peak_charge_only_enabled is False


async def test_schedule_charge_toggle_sends_charge_scope_only():
    vehicle = Vehicle(
        id="v1",
        name="test",
        model="test",
        ev_first_departure_enabled=True,
        ev_first_departure_climate_enabled=True,
        ev_off_peak_start_time=time(22, 0),
        ev_off_peak_end_time=time(7, 0),
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_schedule_charge_enabled("v1", True)
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.first_departure is None
    assert options.second_departure is None
    assert options.climate_enabled is None
    assert options.charging_enabled is True
    assert options.off_peak_start_time is None


async def test_off_peak_charge_only_toggle_sends_charge_scope_only():
    vehicle = Vehicle(
        id="v1", name="test", model="test", ev_first_departure_climate_enabled=True
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_off_peak_charge_only_enabled("v1", False)
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.first_departure is None
    assert options.second_departure is None
    assert options.climate_enabled is None
    assert options.off_peak_charge_only_enabled is False
    assert options.charging_enabled is None


async def test_departure_enable_with_charging_on_skips_charge_scope():
    vehicle = Vehicle(
        id="v1",
        name="test",
        model="test",
        ev_schedule_charge_enabled=True,
        ev_first_departure_enabled=False,
        ev_first_departure_time=time(6, 50),
        ev_first_departure_days=[1, 2, 3, 4, 5],
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_departure_enabled("v1", 1, True)
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.charging_enabled is None
    assert options.off_peak_start_time is None
    assert options.off_peak_end_time is None
    assert options.off_peak_charge_only_enabled is None
    assert options.first_departure.enabled is True
    assert options.first_departure.time == time(6, 50)
    assert options.second_departure.enabled is False


async def test_departure_enable_from_charging_off_forces_reserv_flag():
    vehicle = Vehicle(
        id="v1",
        name="test",
        model="test",
        ev_schedule_charge_enabled=False,
        ev_first_departure_enabled=False,
        ev_first_departure_time=time(6, 50),
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_departure_enabled("v1", 1, True)
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.charging_enabled is True
    assert options.off_peak_start_time == time(0, 0)
    assert options.first_departure.enabled is True


async def test_departure_disable_skips_charge_scope():
    vehicle = Vehicle(
        id="v1", name="test", model="test", ev_schedule_charge_enabled=True
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_departure_enabled("v1", 1, False)
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.charging_enabled is None
    assert options.first_departure.enabled is False


async def test_departure_climate_toggle_uses_climate_scope_only():
    vehicle = Vehicle(
        id="v1",
        name="test",
        model="test",
        ev_schedule_charge_enabled=True,
        ev_first_departure_climate_enabled=None,
    )
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_departure_climate_enabled("v1", 1, True)
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.charging_enabled is None
    assert options.off_peak_charge_only_enabled is None
    assert options.climate_enabled is True


async def test_departure_defrost_toggle_uses_climate_scope_only():
    vehicle = Vehicle(id="v1", name="test", model="test")
    coordinator = _coordinator(vehicle)
    await coordinator.async_set_departure_defrost("v1", 1, True)
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.charging_enabled is None
    assert options.defrost is True
