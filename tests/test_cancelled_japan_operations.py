"""Cancellation must not release a vehicle-operation lock during background work."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from test_region_operation_serialization import coordinator


async def test_cancelled_command_keeps_lock_through_confirmation():
    result = coordinator()
    submitted = asyncio.Event()
    finished = asyncio.Event()
    result.hass.async_add_executor_job.return_value = "synthetic-action"

    async def confirmation(*args):
        submitted.set()
        await finished.wait()

    result.async_await_action_and_refresh = AsyncMock(side_effect=confirmation)
    task = asyncio.create_task(result.async_unlock_vehicle("synthetic"))
    await submitted.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()  # repeated cancellation must not release the lock either
    await asyncio.sleep(0)
    assert result._action_lock.locked()
    assert not task.done()
    with pytest.raises(HomeAssistantError, match="in progress"):
        await result.async_lock_vehicle("synthetic")
    finished.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not result._action_lock.locked()
    result.async_await_action_and_refresh.assert_awaited_once()


async def test_cancelled_capture_still_caches_completed_image():
    result = coordinator()
    started = asyncio.Event()
    finished = asyncio.Event()
    details = SimpleNamespace(captured_at=None, image_bytes=b"synthetic")

    async def capture(*args):
        started.set()
        await finished.wait()
        return details

    result.hass.async_add_executor_job.side_effect = capture
    task = asyncio.create_task(result.async_request_svm_capture("synthetic"))
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert result._action_lock.locked()
    finished.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert result.get_cached_svm_details("synthetic") is details
    result.async_set_updated_data.assert_called_once()
    assert not result._action_lock.locked()


async def test_cancelled_executor_failure_is_drained_before_releasing_lock():
    result = coordinator()
    started = asyncio.Event()
    finished = asyncio.Event()

    async def capture(*args):
        started.set()
        await finished.wait()
        raise ValueError("synthetic worker failure")

    result.hass.async_add_executor_job.side_effect = capture
    task = asyncio.create_task(result.async_request_svm_capture("synthetic"))
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert result._action_lock.locked()
    finished.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not result._action_lock.locked()
    assert result.get_cached_svm_details("synthetic") is None
