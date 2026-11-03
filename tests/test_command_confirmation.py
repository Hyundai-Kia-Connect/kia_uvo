"""Japan distinguishes service acceptance from physical completion and failures."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.exceptions import HomeAssistantError
from hyundai_kia_connect_api.const import ORDER_STATUS
import pytest

from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator
from custom_components.kia_uvo.japan_coordinator import JapanDataUpdateCoordinator


def coordinator(strict=True):
    coordinator_class = (
        JapanDataUpdateCoordinator if strict else HyundaiKiaConnectDataUpdateCoordinator
    )
    result = coordinator_class.__new__(coordinator_class)
    result.vehicle_manager = MagicMock()
    result.vehicle_manager.api = SimpleNamespace(
        supports_remote_commands=True,
        supports_force_refresh=True,
        requires_command_confirmation=strict,
    )
    result.hass = MagicMock()
    result.hass.async_add_executor_job = AsyncMock()
    result.async_check_and_refresh_token = AsyncMock()
    result.async_refresh = AsyncMock()
    result.async_set_updated_data = MagicMock()
    result._action_lock = asyncio.Lock()
    result.data = {}
    return result


@pytest.mark.parametrize(
    "status",
    [
        ORDER_STATUS.FAILED,
        ORDER_STATUS.TIMEOUT,
        ORDER_STATUS.UNKNOWN,
        ORDER_STATUS.PENDING,
        None,
    ],
)
async def test_unconfirmed_command_raises_after_refresh(monkeypatch, status):
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.asyncio.sleep", AsyncMock()
    )
    result = coordinator()
    result.hass.async_add_executor_job.side_effect = ["SYNTHETIC_ID", status, None]
    with pytest.raises(HomeAssistantError, match="not confirmed"):
        await result.async_lock_vehicle("CAR")
    result.async_refresh.assert_not_awaited()
    result.hass.async_add_executor_job.assert_awaited_with(
        result.vehicle_manager.update_all_vehicles_with_cached_state
    )


async def test_confirmed_command_completes(monkeypatch):
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.asyncio.sleep", AsyncMock()
    )
    result = coordinator()
    result.hass.async_add_executor_job.side_effect = [
        "SYNTHETIC_ID",
        ORDER_STATUS.SUCCESS,
        None,
    ]
    await result.async_lock_vehicle("CAR")
    result.async_refresh.assert_not_awaited()
    result.hass.async_add_executor_job.assert_awaited_with(
        result.vehicle_manager.update_all_vehicles_with_cached_state
    )


async def test_older_region_preserves_unknown_confirmation_behavior(monkeypatch):
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.asyncio.sleep", AsyncMock()
    )
    result = coordinator(False)
    result.hass.async_add_executor_job.side_effect = [
        "SYNTHETIC_ID",
        ORDER_STATUS.UNKNOWN,
    ]
    await result.async_lock_vehicle("CAR")
    result.async_refresh.assert_awaited_once()


async def test_forced_refresh_wait_also_checks_confirmation(monkeypatch):
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.asyncio.sleep", AsyncMock()
    )
    result = coordinator()
    result.hass.async_add_executor_job.side_effect = [ORDER_STATUS.FAILED, None]
    with pytest.raises(HomeAssistantError, match="not confirmed"):
        await result.async_await_action_and_force_refresh("CAR", "SYNTHETIC_ID")
    result.async_set_updated_data.assert_called_once()


@pytest.mark.parametrize(
    "status,reason",
    [
        (ORDER_STATUS.FAILED, "service reported failure"),
        (ORDER_STATUS.TIMEOUT, "matching completion reply"),
        (ORDER_STATUS.PENDING, "still pending"),
    ],
)
async def test_confirmation_error_preserves_specific_outcome(
    monkeypatch, status, reason
):
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.asyncio.sleep", AsyncMock()
    )
    result = coordinator()
    result.hass.async_add_executor_job.side_effect = ["SYNTHETIC_ID", status, None]
    with pytest.raises(HomeAssistantError, match=reason):
        await result.async_unlock_vehicle("CAR")
    assert not result._action_lock.locked()


async def test_http_acceptance_completes_without_waiting_for_mqtt(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(
        "custom_components.kia_uvo.japan_coordinator.asyncio.sleep", sleep
    )
    result = coordinator()
    result.hass.async_add_executor_job.side_effect = [
        "SYNTHETIC_ID",
        ORDER_STATUS.ACCEPTED,
        None,
    ]
    await result.async_lock_vehicle("CAR")
    sleep.assert_not_awaited()
    assert result.hass.async_add_executor_job.await_args_list[1].args == (
        result.vehicle_manager.check_action_status,
        "CAR",
        "SYNTHETIC_ID",
        False,
        0,
    )
    result.vehicle_manager.force_refresh_vehicle_state.assert_not_called()
    result.async_set_updated_data.assert_called_once()
    assert not result._action_lock.locked()


async def test_accepted_request_with_state_read_failure_is_labelled_accepted():
    result = coordinator()
    result.hass.async_add_executor_job.side_effect = [
        "SYNTHETIC_ID",
        ORDER_STATUS.ACCEPTED,
        RuntimeError("synthetic failure"),
    ]
    with pytest.raises(HomeAssistantError, match="service accepted the request"):
        await result.async_unlock_vehicle("CAR")
    assert not result._action_lock.locked()


async def test_request_timeout_is_unknown_not_a_reason_to_resend():
    from hyundai_kia_connect_api.exceptions import RequestTimeoutError

    result = coordinator()
    result.hass.async_add_executor_job.side_effect = RequestTimeoutError(
        "synthetic timeout"
    )
    with pytest.raises(HomeAssistantError, match="vehicle execution is unknown"):
        await result.async_unlock_vehicle("CAR")
    assert result.hass.async_add_executor_job.await_count == 1
    assert not result._action_lock.locked()
