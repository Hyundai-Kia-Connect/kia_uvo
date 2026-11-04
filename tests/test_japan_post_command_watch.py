"""Passive watchers must be bounded, reusable and drained before API shutdown."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from test_region_operation_serialization import coordinator

from custom_components.kia_uvo.japan_coordinator import JapanDataUpdateCoordinator


def watcher():
    result = coordinator()
    vehicle = SimpleNamespace(id="synthetic", is_locked=True, enabled=True)
    reader = Mock(return_value=False)
    result.vehicle_manager.api = SimpleNamespace(
        apply_cached_mqtt_state=reader, close=Mock()
    )
    result.vehicle_manager.vehicles = {vehicle.id: vehicle}
    result._POST_COMMAND_WATCH_SECONDS = 4
    result._POST_COMMAND_POLL_INTERVAL_SECONDS = 2
    clock = [0.0]
    result._post_command_watch_clock = lambda: clock[0]

    async def wait(seconds):
        clock[0] += seconds

    async def executor(fn, *args):
        return fn(*args)

    result._async_wait_for_post_command_poll = wait
    result.hass.async_add_executor_job = executor
    result.hass.async_create_background_task = Mock(
        side_effect=lambda coro, name, **kwargs: asyncio.create_task(coro, name=name)
    )
    return result, reader, clock


async def test_new_command_extends_same_passive_watch_window():
    result, reader, clock = watcher()
    rearmed = False

    async def wait(seconds):
        nonlocal rearmed
        clock[0] += seconds
        if not rearmed:
            rearmed = True
            result._start_post_command_state_watch("synthetic")

    result._async_wait_for_post_command_poll = wait
    result._start_post_command_state_watch("synthetic")
    task = result._post_command_watch_tasks["synthetic"]
    await task
    assert clock[0] == 6
    assert reader.call_count == 3
    result.hass.async_create_background_task.assert_called_once()
    assert result.get_post_command_state_diagnostics()[0]["state"] == "finished"
    assert not result._post_command_watch_tasks
    result.async_check_and_refresh_token.assert_not_awaited()


async def test_busy_operation_delays_passive_reader_without_network_work():
    result, reader, clock = watcher()
    await result._action_lock.acquire()

    async def wait(seconds):
        clock[0] += seconds
        if result._action_lock.locked():
            result._action_lock.release()

    result._async_wait_for_post_command_poll = wait
    result._start_post_command_state_watch("synthetic")
    await result._post_command_watch_tasks["synthetic"]
    assert reader.call_count == 1
    result.async_check_and_refresh_token.assert_not_awaited()
    assert not result._action_lock.locked()


async def test_passive_reader_errors_are_private_and_bounded(caplog):
    result, reader, _clock = watcher()
    reader.side_effect = ValueError("SYNTHETIC_SECRET_RESPONSE")
    result._start_post_command_state_watch("synthetic")
    await result._post_command_watch_tasks["synthetic"]
    summary = result.get_post_command_state_diagnostics()
    assert summary[0]["state"] == "finished"
    assert summary[0]["read_errors"] == 2
    assert "SYNTHETIC_SECRET_RESPONSE" not in repr(summary)
    assert "SYNTHETIC_SECRET_RESPONSE" not in caplog.text
    assert caplog.text.count("Japan passive state update could not be applied") == 1
    result.async_set_updated_data.assert_not_called()


async def test_shutdown_drains_active_reader_then_closes_and_rejects_new_watch(
    monkeypatch,
):
    result, _reader, _clock = watcher()
    entered = asyncio.Event()
    release = asyncio.Event()
    close = result.vehicle_manager.api.close
    monkeypatch.setattr(
        "custom_components.kia_uvo.coordinator.DataUpdateCoordinator.async_shutdown",
        AsyncMock(),
    )

    async def executor(fn, *args):
        if fn is result.vehicle_manager.apply_cached_mqtt_state:
            entered.set()
            await release.wait()
            return False
        return fn(*args)

    result.hass.async_add_executor_job = executor
    result._start_post_command_state_watch("synthetic")
    await entered.wait()
    shutdown = asyncio.create_task(result.async_shutdown())
    await asyncio.sleep(0)
    assert result._closing
    close.assert_not_called()
    assert not shutdown.done()
    result._start_post_command_state_watch("synthetic")
    result.hass.async_create_background_task.assert_called_once()
    release.set()
    await shutdown
    close.assert_called_once()
    assert not result._post_command_watch_tasks
    assert result.get_post_command_state_diagnostics()[0]["state"] == "stopped"
    result.async_set_updated_data.assert_not_called()


def test_no_watcher_for_missing_vehicle():
    result, _reader, _clock = watcher()
    result._start_post_command_state_watch("missing")
    result.hass.async_create_background_task.assert_not_called()
    assert JapanDataUpdateCoordinator.get_post_command_state_diagnostics(result) == []


def test_disabled_vehicle_does_not_start_passive_watch():
    result, reader, _clock = watcher()
    result.vehicle_manager.vehicles["synthetic"].enabled = False
    result._start_post_command_state_watch("synthetic")
    result.hass.async_create_background_task.assert_not_called()
    reader.assert_not_called()


async def test_disabling_vehicle_stops_existing_passive_watch():
    result, reader, clock = watcher()

    async def wait(seconds):
        clock[0] += seconds
        result.vehicle_manager.vehicles["synthetic"].enabled = False

    result._async_wait_for_post_command_poll = wait
    result._start_post_command_state_watch("synthetic")
    await result._post_command_watch_tasks["synthetic"]
    assert reader.call_count == 1
    assert (
        result.get_post_command_state_diagnostics()[0]["last_result"]
        == "vehicle_disabled"
    )
    assert not result._post_command_watch_tasks
