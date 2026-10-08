"""Tests for departure scheduling enhancements in kia_uvo.

Validates:
1. Lenient time parsing in services (_parse_time_value).
2. TIME_DESCRIPTIONS in time.py exposes departure time entities.
3. NUMBER_DESCRIPTIONS in number.py exposes departure climate temperature entities.
4. Scope isolation in coordinator between charging and departure schedules.
5. Coordinator departure setters populate options without polluting charging fields.
"""

import datetime as dt
from unittest.mock import MagicMock

import pytest

from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator
from custom_components.kia_uvo.number import (
    FIRST_DEPARTURE_TEMP_KEY,
    NUMBER_DESCRIPTIONS,
    SECOND_DEPARTURE_TEMP_KEY,
)
from custom_components.kia_uvo.services import _parse_time_value
from custom_components.kia_uvo.time import TIME_DESCRIPTIONS


def test_parse_time_value():
    """Verify time parsing handles multiple formats and rejects booleans/empty."""
    assert _parse_time_value(None) is None
    assert _parse_time_value(False) is None
    assert _parse_time_value(True) is None
    assert _parse_time_value("") is None
    assert _parse_time_value("   ") is None
    assert _parse_time_value("none") is None
    assert _parse_time_value("false") is None
    assert _parse_time_value("invalid_time") is None

    assert _parse_time_value("07:30") == dt.time(7, 30)
    assert _parse_time_value("07:30:45") == dt.time(7, 30, 45)
    assert _parse_time_value(dt.time(8, 15)) == dt.time(8, 15)
    assert _parse_time_value(dt.datetime(2026, 1, 1, 9, 45)) == dt.time(9, 45)


def test_time_descriptions_include_departures():
    """Verify departure time entities are properly configured in time.py."""
    keys = {d.key: d for d in TIME_DESCRIPTIONS}
    assert "ev_first_departure_time" in keys
    assert "ev_second_departure_time" in keys

    d1 = keys["ev_first_departure_time"]
    d2 = keys["ev_second_departure_time"]

    mock_vehicle = MagicMock()
    mock_vehicle.ev_first_departure_time = dt.time(7, 30)
    mock_vehicle.ev_second_departure_time = None

    assert d1.value_fn(mock_vehicle) == dt.time(7, 30)
    assert d1.exists_fn(mock_vehicle) is True

    assert d2.value_fn(mock_vehicle) is None
    assert d2.exists_fn(mock_vehicle) is False


def test_number_descriptions_include_departure_temperature():
    """Verify departure temperature entities are configured in number.py."""
    keys = {d.key: d for d in NUMBER_DESCRIPTIONS}
    assert FIRST_DEPARTURE_TEMP_KEY in keys
    assert SECOND_DEPARTURE_TEMP_KEY in keys

    d1 = keys[FIRST_DEPARTURE_TEMP_KEY]
    assert d1.native_min_value == 17
    assert d1.native_max_value == 27
    assert d1.native_step == 0.5


def test_coordinator_scope_isolation():
    """Ensure departure and charge options do not contaminate each other's scopes."""
    mock_vehicle = MagicMock()
    mock_vehicle.ev_first_departure_enabled = True
    mock_vehicle.ev_first_departure_days = [1, 2, 3]
    mock_vehicle.ev_first_departure_time = dt.time(7, 30)
    mock_vehicle.ev_second_departure_enabled = False
    mock_vehicle.ev_second_departure_days = [0]
    mock_vehicle.ev_second_departure_time = dt.time(8, 0)
    mock_vehicle.ev_first_departure_climate_enabled = True
    mock_vehicle.ev_first_departure_climate_temperature = 22.0
    mock_vehicle._ev_first_departure_climate_temperature_unit = 0
    mock_vehicle.ev_first_departure_climate_defrost = False
    mock_vehicle.ev_second_departure_climate_enabled = False
    mock_vehicle.ev_second_departure_climate_temperature = 21.0
    mock_vehicle._ev_second_departure_climate_temperature_unit = 0
    mock_vehicle.ev_second_departure_climate_defrost = False

    mock_vehicle.ev_schedule_charge_enabled = True
    mock_vehicle.ev_off_peak_start_time = dt.time(1, 0)
    mock_vehicle.ev_off_peak_end_time = dt.time(6, 0)
    mock_vehicle.ev_off_peak_charge_only_enabled = True

    coordinator = object.__new__(HyundaiKiaConnectDataUpdateCoordinator)

    # Test departure options builder
    dep_opts = coordinator._build_departure_options_from_vehicle(mock_vehicle)
    assert dep_opts.first_departure.enabled is True
    assert dep_opts.first_departure.time == dt.time(7, 30)
    assert dep_opts.first_departure.climate_enabled is True
    assert dep_opts.first_departure.temperature == 22.0
    assert dep_opts.first_departure.defrost is False
    assert dep_opts.second_departure.climate_enabled is False
    assert dep_opts.second_departure.temperature == 21.0
    assert dep_opts.second_departure.defrost is False
    # Charging scope must be None
    assert dep_opts.charging_enabled is None
    assert dep_opts.off_peak_start_time is None
    assert dep_opts.off_peak_end_time is None
    assert dep_opts.off_peak_charge_only_enabled is None

    # Test charge options builder
    charge_opts = coordinator._build_charge_options_from_vehicle(mock_vehicle)
    assert charge_opts.charging_enabled is True
    assert charge_opts.off_peak_start_time == dt.time(1, 0)
    assert charge_opts.off_peak_end_time == dt.time(6, 0)
    assert charge_opts.off_peak_charge_only_enabled is True
    # Departure & climate scope must be None
    assert charge_opts.first_departure is None
    assert charge_opts.second_departure is None
    assert charge_opts.climate_enabled is None
    assert charge_opts.temperature is None
    assert charge_opts.defrost is None


@pytest.mark.asyncio
async def test_coordinator_async_set_departure_schedule():
    """Verify async_set_departure_schedule updates slot and dispatches schedule."""
    coordinator = object.__new__(HyundaiKiaConnectDataUpdateCoordinator)
    coordinator.vehicle_manager = MagicMock()
    mock_vehicle = MagicMock()
    mock_vehicle.id = "car-1"
    mock_vehicle.ev_first_departure_enabled = False
    mock_vehicle.ev_first_departure_days = [0]
    mock_vehicle.ev_first_departure_time = dt.time(6, 0)
    mock_vehicle.ev_second_departure_enabled = False
    mock_vehicle.ev_second_departure_days = [0]
    mock_vehicle.ev_second_departure_time = dt.time(6, 0)
    mock_vehicle.ev_first_departure_climate_enabled = False
    mock_vehicle.ev_first_departure_climate_temperature = 21.0
    mock_vehicle._ev_first_departure_climate_temperature_unit = 0
    mock_vehicle.ev_first_departure_climate_defrost = False
    mock_vehicle.ev_second_departure_climate_enabled = False
    mock_vehicle.ev_second_departure_climate_temperature = 21.0
    mock_vehicle._ev_second_departure_climate_temperature_unit = 0
    mock_vehicle.ev_second_departure_climate_defrost = False
    coordinator.vehicle_manager.vehicles = {"car-1": mock_vehicle}

    captured_options = []

    async def mock_schedule(vid, opts):
        captured_options.append((vid, opts))

    coordinator.async_schedule_charging_and_climate = mock_schedule

    await coordinator.async_set_departure_schedule(
        "car-1",
        departure_num=1,
        enabled=True,
        days=[1, 2, 3, 4, 5],
        time=dt.time(7, 45),
        climate_enabled=True,
        temperature=22.5,
        defrost=True,
    )

    assert len(captured_options) == 1
    vid, opts = captured_options[0]
    assert vid == "car-1"
    assert opts.first_departure.enabled is True
    assert opts.first_departure.days == [1, 2, 3, 4, 5]
    assert opts.first_departure.time == dt.time(7, 45)
    assert opts.first_departure.climate_enabled is True
    assert opts.first_departure.temperature == 22.5
    assert opts.first_departure.defrost is True
    assert opts.second_departure.enabled is False
    assert opts.second_departure.climate_enabled is False
    assert opts.second_departure.temperature == 21.0
    assert opts.second_departure.defrost is False
    # Charging scope preserved as None
    assert opts.charging_enabled is None


@pytest.mark.asyncio
async def test_coordinator_departure_slot2_isolation():
    """Verify modifying departure 2 does not alter departure 1."""
    coordinator = object.__new__(HyundaiKiaConnectDataUpdateCoordinator)
    coordinator.vehicle_manager = MagicMock()
    mock_vehicle = MagicMock()
    mock_vehicle.id = "car-1"
    mock_vehicle.ev_first_departure_enabled = True
    mock_vehicle.ev_first_departure_days = [1, 2, 3]
    mock_vehicle.ev_first_departure_time = dt.time(7, 30)
    mock_vehicle.ev_first_departure_climate_enabled = True
    mock_vehicle.ev_first_departure_climate_temperature = 23.0
    mock_vehicle._ev_first_departure_climate_temperature_unit = 0
    mock_vehicle.ev_first_departure_climate_defrost = True

    mock_vehicle.ev_second_departure_enabled = False
    mock_vehicle.ev_second_departure_days = [9]
    mock_vehicle.ev_second_departure_time = dt.time(8, 0)
    mock_vehicle.ev_second_departure_climate_enabled = False
    mock_vehicle.ev_second_departure_climate_temperature = 20.0
    mock_vehicle._ev_second_departure_climate_temperature_unit = 0
    mock_vehicle.ev_second_departure_climate_defrost = False
    coordinator.vehicle_manager.vehicles = {"car-1": mock_vehicle}

    captured_options = []

    async def mock_schedule(vid, opts):
        captured_options.append((vid, opts))

    coordinator.async_schedule_charging_and_climate = mock_schedule

    # Change only slot 2
    await coordinator.async_set_departure_schedule(
        "car-1",
        departure_num=2,
        enabled=True,
        days=[0, 6],
        time=dt.time(9, 15),
        climate_enabled=True,
        temperature=19.5,
        defrost=False,
    )

    assert len(captured_options) == 1
    _, opts = captured_options[0]
    # Departure 1 is completely preserved
    assert opts.first_departure.enabled is True
    assert opts.first_departure.days == [1, 2, 3]
    assert opts.first_departure.time == dt.time(7, 30)
    assert opts.first_departure.climate_enabled is True
    assert opts.first_departure.temperature == 23.0
    assert opts.first_departure.defrost is True

    # Departure 2 is updated
    assert opts.second_departure.enabled is True
    assert opts.second_departure.days == [0, 6]
    assert opts.second_departure.time == dt.time(9, 15)
    assert opts.second_departure.climate_enabled is True
    assert opts.second_departure.temperature == 19.5
    assert opts.second_departure.defrost is False


@pytest.mark.asyncio
async def test_coordinator_toggle_departure_day():
    """Verify toggling repeat days for a departure slot."""
    coordinator = object.__new__(HyundaiKiaConnectDataUpdateCoordinator)
    coordinator.vehicle_manager = MagicMock()
    mock_vehicle = MagicMock()
    mock_vehicle.id = "car-1"
    mock_vehicle.ev_first_departure_enabled = True
    mock_vehicle.ev_first_departure_days = [1, 2]  # Mon, Tue
    mock_vehicle.ev_first_departure_time = dt.time(7, 0)
    mock_vehicle.ev_first_departure_climate_enabled = False
    mock_vehicle.ev_first_departure_climate_temperature = 21.0
    mock_vehicle.ev_first_departure_climate_defrost = False

    mock_vehicle.ev_second_departure_enabled = False
    mock_vehicle.ev_second_departure_days = [9]
    mock_vehicle.ev_second_departure_time = dt.time(8, 0)
    mock_vehicle.ev_second_departure_climate_enabled = False
    mock_vehicle.ev_second_departure_climate_temperature = 21.0
    mock_vehicle.ev_second_departure_climate_defrost = False
    coordinator.vehicle_manager.vehicles = {"car-1": mock_vehicle}

    captured_options = []

    async def mock_schedule(vid, opts):
        captured_options.append((vid, opts))

    coordinator.async_schedule_charging_and_climate = mock_schedule

    # Toggle Wednesday (3) ON
    await coordinator.async_toggle_departure_day("car-1", departure_num=1, day=3, enabled=True, debounce=False)
    assert len(captured_options) == 1
    assert captured_options[0][1].first_departure.days == [1, 2, 3]

    # Toggle Monday (1) OFF
    mock_vehicle.ev_first_departure_days = [1, 2, 3]
    captured_options.clear()
    await coordinator.async_toggle_departure_day("car-1", departure_num=1, day=1, enabled=False, debounce=False)
    assert len(captured_options) == 1
    assert captured_options[0][1].first_departure.days == [2, 3]

    # Toggle remaining off -> reverts to [9]
    mock_vehicle.ev_first_departure_days = [2]
    captured_options.clear()
    await coordinator.async_toggle_departure_day("car-1", departure_num=1, day=2, enabled=False, debounce=False)
    assert len(captured_options) == 1
    assert captured_options[0][1].first_departure.days == [9]


@pytest.mark.asyncio
async def test_coordinator_departure_debounce_coalescing():
    """Verify multiple rapid departure changes coalesce into a single batched API call."""
    coordinator = object.__new__(HyundaiKiaConnectDataUpdateCoordinator)
    coordinator.vehicle_manager = MagicMock()
    mock_vehicle = MagicMock()
    mock_vehicle.id = "car-1"
    mock_vehicle.ev_first_departure_enabled = False
    mock_vehicle.ev_first_departure_days = [9]
    mock_vehicle.ev_first_departure_time = dt.time(6, 0)
    mock_vehicle.ev_first_departure_climate_enabled = False
    mock_vehicle.ev_first_departure_climate_temperature = 21.0
    mock_vehicle.ev_first_departure_climate_defrost = False

    mock_vehicle.ev_second_departure_enabled = False
    mock_vehicle.ev_second_departure_days = [9]
    mock_vehicle.ev_second_departure_time = dt.time(8, 0)
    mock_vehicle.ev_second_departure_climate_enabled = False
    mock_vehicle.ev_second_departure_climate_temperature = 21.0
    mock_vehicle.ev_second_departure_climate_defrost = False
    coordinator.vehicle_manager.vehicles = {"car-1": mock_vehicle}

    captured_options = []

    async def mock_schedule(vid, opts):
        captured_options.append((vid, opts))

    coordinator.async_schedule_charging_and_climate = mock_schedule

    # Perform 4 rapid edits with debounce=True (default)
    await coordinator.async_set_departure_temperature("car-1", departure_num=1, temperature=23.5)
    await coordinator.async_set_departure_climate_enabled("car-1", departure_num=1, enabled=True)
    await coordinator.async_set_departure_defrost("car-1", departure_num=1, enabled=True)
    await coordinator.async_set_departure_days("car-1", departure_num=1, days=[1, 2, 3, 4, 5])

    # 1. Verify in-memory vehicle state was optimistically updated immediately
    assert mock_vehicle.ev_first_departure_climate_temperature == 23.5
    assert mock_vehicle.ev_first_departure_climate_enabled is True
    assert mock_vehicle.ev_first_departure_climate_defrost is True
    assert mock_vehicle.ev_first_departure_days == [1, 2, 3, 4, 5]

    # 2. Verify no remote API calls have been fired yet (waiting in debounce buffer)
    assert len(captured_options) == 0

    # 3. Flush the debounce queue
    await coordinator.async_flush_departure_update("car-1")

    # 4. Verify exactly ONE atomic remote call was dispatched with all combined parameters
    assert len(captured_options) == 1
    vid, opts = captured_options[0]
    assert vid == "car-1"
    assert opts.first_departure.temperature == 23.5
    assert opts.first_departure.climate_enabled is True
    assert opts.first_departure.defrost is True
    assert opts.first_departure.days == [1, 2, 3, 4, 5]
    # Departure 2 untouched
    assert opts.second_departure.temperature == 21.0
    assert opts.second_departure.climate_enabled is False
    assert opts.second_departure.defrost is False



def test_departure_day_switch_descriptions():
    """Verify all 14 departure day switches exist and map to correct days."""
    from custom_components.kia_uvo.switch import SWITCH_DESCRIPTIONS

    switch_map = {d.key: d for d in SWITCH_DESCRIPTIONS}

    mock_vehicle = MagicMock()
    mock_vehicle.ev_first_departure_days = [1, 3, 5]  # Mon, Wed, Fri
    mock_vehicle.ev_first_departure_enabled = True
    mock_vehicle.ev_second_departure_days = [0, 6]    # Sun, Sat
    mock_vehicle.ev_second_departure_enabled = True

    # Slot 1 day checks
    assert "ev_first_departure_day_mon" in switch_map
    assert switch_map["ev_first_departure_day_mon"].value_fn(mock_vehicle) is True
    assert switch_map["ev_first_departure_day_tue"].value_fn(mock_vehicle) is False
    assert switch_map["ev_first_departure_day_wed"].value_fn(mock_vehicle) is True
    assert switch_map["ev_first_departure_day_thu"].value_fn(mock_vehicle) is False
    assert switch_map["ev_first_departure_day_fri"].value_fn(mock_vehicle) is True
    assert switch_map["ev_first_departure_day_sat"].value_fn(mock_vehicle) is False
    assert switch_map["ev_first_departure_day_sun"].value_fn(mock_vehicle) is False

    # Slot 2 day checks
    assert "ev_second_departure_day_sun" in switch_map
    assert switch_map["ev_second_departure_day_mon"].value_fn(mock_vehicle) is False
    assert switch_map["ev_second_departure_day_sat"].value_fn(mock_vehicle) is True
    assert switch_map["ev_second_departure_day_sun"].value_fn(mock_vehicle) is True


def test_departure_repeat_select_descriptions():
    """Verify departure repeat select options, mapping, and presets."""
    from custom_components.kia_uvo.select import (
        PRESET_CUSTOM,
        PRESET_EVERYDAY,
        PRESET_MON_FRI,
        PRESET_NEVER,
        PRESET_SAT_SUN,
        SELECT_DESCRIPTIONS,
        _days_to_preset,
    )

    # Test preset mapper
    assert _days_to_preset([0, 1, 2, 3, 4, 5, 6]) == PRESET_EVERYDAY
    assert _days_to_preset([1, 2, 3, 4, 5]) == PRESET_MON_FRI
    assert _days_to_preset([0, 6]) == PRESET_SAT_SUN
    assert _days_to_preset([9]) == PRESET_NEVER
    assert _days_to_preset([]) == PRESET_NEVER
    assert _days_to_preset(None) == PRESET_NEVER
    assert _days_to_preset([1, 3, 5]) == PRESET_CUSTOM

    select_map = {d.key: d for d in SELECT_DESCRIPTIONS}
    assert "ev_first_departure_repeat" in select_map
    assert "ev_second_departure_repeat" in select_map

    mock_vehicle = MagicMock()
    mock_vehicle.ev_first_departure_days = [1, 2, 3, 4, 5]
    mock_vehicle.ev_second_departure_days = [9]

    assert select_map["ev_first_departure_repeat"].value_fn(mock_vehicle) == PRESET_MON_FRI
    assert select_map["ev_second_departure_repeat"].value_fn(mock_vehicle) == PRESET_NEVER


@pytest.mark.asyncio
async def test_service_handle_set_departure_schedule():
    """Verify async_handle_set_departure_schedule parses input robustly and dispatches to coordinator."""
    from custom_components.kia_uvo.services import async_setup_services
    from homeassistant.core import ServiceCall

    mock_hass = MagicMock()
    registered_services = {}

    def mock_register(domain, service_name, handler, schema=None):
        registered_services[service_name] = handler

    mock_hass.services.async_register = mock_register
    async_setup_services(mock_hass)

    assert "set_departure_schedule" in registered_services
    handler = registered_services["set_departure_schedule"]

    mock_coordinator = MagicMock()
    mock_coordinator.async_set_departure_schedule = MagicMock()

    async def mock_async_set(*args, **kwargs):
        pass

    mock_coordinator.async_set_departure_schedule.side_effect = mock_async_set

    mock_vehicle = MagicMock()
    mock_vehicle.id = "veh-123"
    mock_coordinator.vehicle_manager.vehicles = {"veh-123": mock_vehicle}

    mock_dev_entry = MagicMock()
    mock_dev_entry.config_entries = {"entry-1"}
    mock_hass.data = {
        "kia_uvo": {
            "entry-1": mock_coordinator,
        }
    }
    mock_hass.helpers.device_registry.async_get.return_value.async_get.return_value = mock_dev_entry

    service_call = MagicMock(
        domain="kia_uvo",
        service="set_departure_schedule",
        data={
            "device_id": "dev-1",
            "departure_num": "1",
            "enabled": True,
            "time": "08:15",
            "days": ["1", "2", "3", "4", "5"],
            "climate_enabled": "true",
            "temperature": "23.5",
            "defrost": "false",
        },
    )

    await handler(service_call)

    mock_coordinator.async_set_departure_schedule.assert_called_once_with(
        "veh-123",
        departure_num=1,
        enabled=True,
        days=[1, 2, 3, 4, 5],
        time=dt.time(8, 15),
        climate_enabled=True,
        temperature=23.5,
        temperature_unit=None,
        defrost=False,
    )



