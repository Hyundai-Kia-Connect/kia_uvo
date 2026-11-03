"""Japan lifecycle guards preserve current upstream polling and device settings."""

import asyncio
from unittest.mock import AsyncMock, Mock

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.exceptions import ServiceTemporaryUnavailable
import pytest
from test_region_operation_serialization import coordinator

from custom_components.kia_uvo.japan_coordinator import JapanDataUpdateCoordinator


async def test_japan_cached_poll_preserves_upstream_vehicle_failure_isolation():
    result = coordinator()
    result.vehicle_manager.vehicles = {
        key: Vehicle(id=key, name=key) for key in ("failed", "healthy")
    }
    result._failed_vehicles = set()
    result._vehicle_failures = {}
    result.vehicle_manager.update_vehicle_with_cached_state.side_effect = [
        ServiceTemporaryUnavailable("synthetic backend error"),
        None,
    ]

    async def executor(fn, *args):
        assert result._action_lock.locked()
        return fn(*args)

    result.hass.async_add_executor_job = executor
    await result.async_update_all()
    assert not result.vehicle_available("failed")
    assert result.vehicle_available("healthy")
    assert result.vehicle_manager.update_vehicle_with_cached_state.call_count == 2
    result.vehicle_manager.update_all_vehicles_with_cached_state.assert_not_called()
    result.async_set_updated_data.assert_called_once_with(result.data)


@pytest.mark.parametrize("method", ["async_update_all", "async_force_update_all"])
async def test_japan_poll_cancellation_keeps_lock_until_upstream_work_finishes(method):
    result = coordinator()
    started, release = asyncio.Event(), asyncio.Event()

    async def poll(*, mode):
        assert mode == ("cached" if method == "async_update_all" else "force")
        started.set()
        await release.wait()

    result._async_poll_vehicles = AsyncMock(side_effect=poll)
    task = asyncio.create_task(getattr(result, method)())
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert result._action_lock.locked()
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not result._action_lock.locked()
    result.async_set_updated_data.assert_called_once_with(result.data)


async def test_japan_token_check_preserves_upstream_device_enabled_sync():
    result = coordinator()
    result._async_save_token = AsyncMock()
    result._sync_vehicle_enabled_states = Mock()
    await JapanDataUpdateCoordinator.async_check_and_refresh_token(result)
    result.hass.async_add_executor_job.assert_awaited_once_with(
        result.vehicle_manager.check_and_refresh_token
    )
    result._async_save_token.assert_awaited_once()
    result._sync_vehicle_enabled_states.assert_called_once_with()
