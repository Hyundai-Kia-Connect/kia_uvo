"""Japan MQTT commands, token refresh, and status polling share one operation lock."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from hyundai_kia_connect_api.const import ORDER_STATUS

from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator
from custom_components.kia_uvo.japan_coordinator import JapanDataUpdateCoordinator


def coordinator(strict=True):
    coordinator_class = (
        JapanDataUpdateCoordinator if strict else HyundaiKiaConnectDataUpdateCoordinator
    )
    result = coordinator_class.__new__(coordinator_class)
    result.vehicle_manager = MagicMock()
    result.vehicle_manager.api = SimpleNamespace(
        requires_command_confirmation=strict,
        supports_remote_commands=True,
        supports_force_refresh=True,
        supported_commands=None,
    )
    result._action_lock = asyncio.Lock()
    result.data = {}
    result.hass = MagicMock()
    result.hass.async_add_executor_job = AsyncMock()
    result.async_check_and_refresh_token = AsyncMock()
    result.async_set_updated_data = MagicMock()
    result.async_refresh = AsyncMock()
    result._svm_details = {}
    result._svm_received_at = {}
    result._svm_views = {}
    return result


async def test_periodic_poll_skips_busy_japan_without_token_or_network_calls():
    result = coordinator()
    result._async_update_data_unlocked = AsyncMock()
    async with result._action_lock:
        assert await result._async_update_data() == {}
    result._async_update_data_unlocked.assert_not_awaited()
    result.async_check_and_refresh_token.assert_not_awaited()


async def test_periodic_poll_holds_lock_during_token_and_status_work():
    result = coordinator()

    async def work():
        assert result._action_lock.locked()
        return {}

    result._async_update_data_unlocked = AsyncMock(side_effect=work)
    await result._async_update_data()
    assert not result._action_lock.locked()


@pytest.mark.parametrize(
    "method,args",
    [
        ("async_force_update_all", ()),
        ("async_force_refresh_vehicle", ("synthetic",)),
        ("async_update_all", ()),
        ("async_request_svm_capture", ("synthetic",)),
    ],
)
async def test_manual_operations_reject_busy_before_token_refresh(method, args):
    result = coordinator()
    async with result._action_lock:
        with pytest.raises(HomeAssistantError, match="operation is in progress"):
            await getattr(result, method)(*args)
    result.async_check_and_refresh_token.assert_not_awaited()
    result.hass.async_add_executor_job.assert_not_awaited()


async def test_svm_capture_refreshes_token_while_holding_lock():
    result = coordinator()

    async def refresh_token():
        assert result._action_lock.locked()

    result.async_check_and_refresh_token.side_effect = refresh_token
    result.hass.async_add_executor_job.return_value = "synthetic-details"
    assert await result.async_request_svm_capture("synthetic") == "synthetic-details"
    result.async_check_and_refresh_token.assert_awaited_once()
    assert not result._action_lock.locked()


async def test_command_poll_and_manual_force_cannot_replace_active_session(monkeypatch):
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.asyncio.sleep", AsyncMock()
    )
    result = coordinator()
    started, release = asyncio.Event(), asyncio.Event()

    async def job(fn, *args):
        assert result._action_lock.locked()
        if fn is result.vehicle_manager.check_action_status:
            started.set()
            await release.wait()
            return ORDER_STATUS.SUCCESS
        if fn is result.vehicle_manager.update_all_vehicles_with_cached_state:
            return None
        return "synthetic-action"

    result.hass.async_add_executor_job.side_effect = job
    command = asyncio.create_task(result.async_lock_vehicle("synthetic"))
    await started.wait()
    assert await result._async_update_data() == {}
    with pytest.raises(HomeAssistantError, match="operation is in progress"):
        await result.async_force_refresh_vehicle("synthetic")
    release.set()
    await asyncio.wait_for(command, timeout=1)
    result.async_refresh.assert_not_awaited()
    result.async_check_and_refresh_token.assert_awaited_once()
    assert not result._action_lock.locked()


async def test_confirmed_command_telemetry_failure_is_reported_accurately(monkeypatch):
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.asyncio.sleep", AsyncMock()
    )
    result = coordinator()
    result.hass.async_add_executor_job.side_effect = [
        "synthetic-action",
        ORDER_STATUS.SUCCESS,
        RuntimeError("synthetic private response"),
    ]
    with pytest.raises(
        HomeAssistantError, match="command completed, but updated telemetry"
    ) as caught:
        await result.async_lock_vehicle("synthetic")
    assert "private response" not in str(caught.value)
    assert not result._action_lock.locked()


async def test_unconfirmed_result_remains_unconfirmed_if_refresh_also_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.asyncio.sleep", AsyncMock()
    )
    result = coordinator()
    result.hass.async_add_executor_job.side_effect = [
        "synthetic-action",
        ORDER_STATUS.FAILED,
        RuntimeError("synthetic private response"),
    ]
    with pytest.raises(HomeAssistantError, match="completion was not confirmed"):
        await result.async_lock_vehicle("synthetic")
    assert not result._action_lock.locked()


async def test_older_region_uses_original_coordinator_class():
    result = coordinator(False)
    assert type(result) is HyundaiKiaConnectDataUpdateCoordinator
    assert not hasattr(result, "_async_region_operation")
    assert "async_shutdown" not in HyundaiKiaConnectDataUpdateCoordinator.__dict__
