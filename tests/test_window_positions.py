"""Vehicle profiles limit window controls without suppressing rear telemetry."""

from unittest.mock import AsyncMock, MagicMock

from conftest import make_coordinator, make_hass
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import WINDOW_STATE

from custom_components.kia_uvo import binary_sensor, cover
from custom_components.kia_uvo.japan_coordinator import JapanDataUpdateCoordinator


def vehicle(positions):
    result = Vehicle(id="synthetic", name="synthetic", model="synthetic")
    result.supports_window_control = True
    result.supported_window_positions = positions
    result.front_left_window_is_open = False
    result.front_right_window_is_open = False
    result.back_left_window_is_open = True
    result.back_right_window_is_open = False
    return result


async def test_front_only_profile_omits_rear_controls_but_keeps_rear_telemetry():
    result = vehicle(("front_left", "front_right"))
    coordinator = make_coordinator(result)
    coordinator.__class__ = JapanDataUpdateCoordinator
    coordinator.supports_command = lambda command: command == "set_windows_state"
    hass, entry = make_hass(coordinator)
    controls = []
    await cover.async_setup_entry(hass, entry, controls.extend)
    assert {entity.entity_description.window_position for entity in controls} == {
        "front_left",
        "front_right",
    }
    telemetry = []
    await binary_sensor.async_setup_entry(hass, entry, telemetry.extend)
    states = {entity.entity_description.key: entity.is_on for entity in telemetry}
    assert states["back_left_window_is_open"] is True
    assert states["back_right_window_is_open"] is False


async def test_legacy_unspecified_positions_keeps_all_covers():
    result = vehicle(None)
    hass, entry = make_hass(make_coordinator(result))
    controls = []
    await cover.async_setup_entry(hass, entry, controls.extend)
    assert {entity.entity_description.window_position for entity in controls} == {
        "front_left",
        "front_right",
        "back_left",
        "back_right",
    }


async def test_vent_all_windows_targets_only_profile_supported_positions():
    coordinator = JapanDataUpdateCoordinator.__new__(JapanDataUpdateCoordinator)
    coordinator.vehicle_manager = MagicMock()
    coordinator.vehicle_manager.vehicles = {
        "synthetic": vehicle(("front_left", "front_right"))
    }
    coordinator._async_send_action = AsyncMock()
    await coordinator.async_vent_all_windows("synthetic")
    _vehicle_id, action, _label = coordinator._async_send_action.call_args.args
    action()
    _vehicle_id, options = coordinator.vehicle_manager.set_windows_state.call_args.args
    assert options.front_left == WINDOW_STATE.VENTILATION
    assert options.front_right == WINDOW_STATE.VENTILATION
    assert options.back_left is None
    assert options.back_right is None


async def test_non_japan_does_not_filter_covers_using_japan_profile_metadata():
    result = vehicle(("front_left", "front_right"))
    hass, entry = make_hass(make_coordinator(result))
    controls = []
    await cover.async_setup_entry(hass, entry, controls.extend)
    assert {entity.entity_description.window_position for entity in controls} == {
        "front_left",
        "front_right",
        "back_left",
        "back_right",
    }
