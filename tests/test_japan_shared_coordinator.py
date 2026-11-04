"""Japan uses existing setup, commands and polling without a regional coordinator."""

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, sentinel

from homeassistant.exceptions import HomeAssistantError
from hyundai_kia_connect_api import ClimateRequestOptions, SVMDetails, Vehicle
from hyundai_kia_connect_api.exceptions import RequestTimeoutError
import pytest

from custom_components import kia_uvo
from custom_components.kia_uvo import coordinator as coordinator_module
from custom_components.kia_uvo.const import DOMAIN
from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator


@pytest.fixture
def shared_coordinator(monkeypatch):
    result = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    result.hass = MagicMock()

    async def executor(target, *args):
        return target(*args)

    result.hass.async_add_executor_job = AsyncMock(side_effect=executor)
    vehicle = Vehicle(id="japan-test", name="test")
    vehicle.is_locked = True
    vehicle.air_control_is_on = False
    vehicle.ev_charge_port_door_is_open = False
    vehicle.ev_charge_limits_ac = 100
    vehicle.ev_charge_limits_dc = 80
    result.vehicle_manager = MagicMock()
    result.vehicle_manager.vehicles = {vehicle.id: vehicle}
    result.vehicle_manager.check_action_status.return_value = sentinel.service_accepted
    result._action_lock = asyncio.Lock()
    result._failed_vehicles = set()
    result._vehicle_failures = {}
    result.force_refresh_interval = 5400
    result._svm_details = {}
    result.data = {}
    result.async_check_and_refresh_token = AsyncMock()
    result.async_set_updated_data = MagicMock()

    async def cached_refresh():
        await result._async_poll_vehicles(mode="cached")
        result.async_set_updated_data(result.data)

    result.async_refresh = AsyncMock(side_effect=cached_refresh)
    monkeypatch.setattr(coordinator_module.asyncio, "sleep", AsyncMock())
    return result


async def test_japan_setup_uses_exact_existing_coordinator(
    monkeypatch, shared_coordinator
):
    entry = MagicMock(unique_id="japan-entry", data={"region": 10, "brand": 2})
    hass = MagicMock(data={})
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    shared_coordinator.async_config_entry_first_refresh = AsyncMock()
    constructor = MagicMock(return_value=shared_coordinator)
    monkeypatch.setattr(kia_uvo, "HyundaiKiaConnectDataUpdateCoordinator", constructor)
    services = MagicMock()
    monkeypatch.setattr(kia_uvo, "async_setup_services", services)

    assert await kia_uvo.async_setup_entry(hass, entry)

    constructor.assert_called_once_with(hass, entry)
    assert (
        type(hass.data[DOMAIN][entry.unique_id])
        is HyundaiKiaConnectDataUpdateCoordinator
    )
    shared_coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, kia_uvo.PLATFORMS
    )
    services.assert_called_once_with(hass)


@pytest.mark.parametrize(
    ("coordinator_method", "manager_method", "arguments"),
    [
        ("async_lock_vehicle", "lock", ()),
        ("async_unlock_vehicle", "unlock", ()),
        ("async_start_climate", "start_climate", (ClimateRequestOptions(set_temp=22),)),
        ("async_stop_climate", "stop_climate", ()),
        ("async_open_charge_port", "open_charge_port", ()),
        ("async_close_charge_port", "close_charge_port", ()),
        ("async_set_charge_limits", "set_charge_limits", (70, 80)),
        ("async_set_charge_limits", "set_charge_limits", (100, 70)),
    ],
)
async def test_japan_service_acceptance_refreshes_without_retry_or_invented_state(
    shared_coordinator, coordinator_method, manager_method, arguments
):
    manager = shared_coordinator.vehicle_manager
    vehicle = manager.vehicles["japan-test"]
    before = (
        vehicle.is_locked,
        vehicle.air_control_is_on,
        vehicle.ev_charge_port_door_is_open,
        vehicle.ev_charge_limits_ac,
        vehicle.ev_charge_limits_dc,
    )
    getattr(manager, manager_method).return_value = "accepted-request"

    await getattr(shared_coordinator, coordinator_method)(vehicle.id, *arguments)

    getattr(manager, manager_method).assert_called_once_with(vehicle.id, *arguments)
    manager.check_action_status.assert_called_once_with(
        vehicle.id, "accepted-request", True, 60
    )
    manager.update_vehicle_with_cached_state.assert_called_once_with(vehicle.id)
    manager.force_refresh_vehicle_state.assert_not_called()
    assert (
        vehicle.is_locked,
        vehicle.air_control_is_on,
        vehicle.ev_charge_port_door_is_open,
        vehicle.ev_charge_limits_ac,
        vehicle.ev_charge_limits_dc,
    ) == before
    shared_coordinator.async_set_updated_data.assert_called_once_with(
        shared_coordinator.data
    )


async def test_japan_command_timeout_is_not_retried(shared_coordinator):
    manager = shared_coordinator.vehicle_manager
    manager.unlock.side_effect = RequestTimeoutError("synthetic timeout")

    with pytest.raises(HomeAssistantError, match="Failed to unlock vehicle"):
        await shared_coordinator.async_unlock_vehicle("japan-test")

    manager.unlock.assert_called_once_with("japan-test")
    manager.check_action_status.assert_not_called()
    manager.update_vehicle_with_cached_state.assert_not_called()


@pytest.mark.parametrize(
    ("coordinator_method", "manager_method"),
    [
        ("async_update_all", "update_vehicle_with_cached_state"),
        ("async_force_update_all", "force_refresh_vehicle_state"),
    ],
)
async def test_japan_poll_delegates_cached_and_explicit_force(
    shared_coordinator, coordinator_method, manager_method
):
    await getattr(shared_coordinator, coordinator_method)()

    manager = shared_coordinator.vehicle_manager
    getattr(manager, manager_method).assert_called_once_with("japan-test")
    manager.check_and_force_update_vehicle.assert_not_called()
    shared_coordinator.async_check_and_refresh_token.assert_awaited_once()
    shared_coordinator.async_set_updated_data.assert_called_once_with(
        shared_coordinator.data
    )


async def test_japan_svm_capture_uses_existing_cache(shared_coordinator):
    details = SVMDetails(
        image_bytes=b"synthetic image",
        captured_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    )
    shared_coordinator.vehicle_manager.request_svm_capture.return_value = details

    assert await shared_coordinator.async_request_svm_capture("japan-test") is details
    assert shared_coordinator.get_cached_svm_details("japan-test") is details
    shared_coordinator.vehicle_manager.request_svm_capture.assert_called_once_with(
        "japan-test", True
    )
    shared_coordinator.async_set_updated_data.assert_called_once_with(
        shared_coordinator.data
    )
