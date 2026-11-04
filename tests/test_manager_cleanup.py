"""Shared coordinator shutdown closes managers without regional setup changes."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import pytest

from custom_components import kia_uvo
from custom_components.kia_uvo.const import DOMAIN
from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator


@pytest.fixture
def stop_polling(monkeypatch):
    result = AsyncMock()
    monkeypatch.setattr(DataUpdateCoordinator, "async_shutdown", result)
    return result


def coordinator(manager):
    result = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    result.hass = SimpleNamespace(
        async_add_executor_job=AsyncMock(side_effect=lambda target: target())
    )
    result.vehicle_manager = manager
    result._action_lock = asyncio.Lock()
    return result


def unload_fixture(coordinator, *, platform_success=True):
    hass = SimpleNamespace(
        data={DOMAIN: {"synthetic-entry": coordinator}},
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=platform_success)
        ),
    )
    return hass, SimpleNamespace(unique_id="synthetic-entry")


async def test_shutdown_waits_for_active_command_and_closes_off_loop(stop_polling):
    events = []
    loop_thread = threading.get_ident()
    close_threads = []
    stopping = asyncio.Event()

    async def polling():
        events.append("polling_stopped")
        stopping.set()

    stop_polling.side_effect = polling

    def close():
        events.append("manager_closed")
        close_threads.append(threading.get_ident())

    result = coordinator(SimpleNamespace(close=close))
    result.hass.async_add_executor_job.side_effect = asyncio.to_thread
    async with result._action_lock:
        task = asyncio.create_task(result.async_shutdown())
        await stopping.wait()
        assert close_threads == []
        events.append("command_finished")
    await task

    assert events == ["polling_stopped", "command_finished", "manager_closed"]
    assert close_threads[0] != loop_thread


async def test_older_library_without_manager_close_still_stops_polling(stop_polling):
    result = coordinator(SimpleNamespace())

    await result.async_shutdown()

    stop_polling.assert_awaited_once()
    result.hass.async_add_executor_job.assert_not_awaited()


async def test_successful_unload_closes_only_that_manager(monkeypatch, stop_polling):
    close = Mock()
    other_close = Mock()
    result = coordinator(SimpleNamespace(close=close))
    hass, entry = unload_fixture(result)
    hass.data[DOMAIN]["other-entry"] = coordinator(SimpleNamespace(close=other_close))
    services = Mock()
    monkeypatch.setattr(kia_uvo, "async_unload_services", services)

    assert await kia_uvo.async_unload_entry(hass, entry)

    close.assert_called_once()
    other_close.assert_not_called()
    assert list(hass.data[DOMAIN]) == ["other-entry"]
    services.assert_not_called()


async def test_failed_platform_unload_leaves_manager_running(stop_polling):
    close = Mock()
    result = coordinator(SimpleNamespace(close=close))
    hass, entry = unload_fixture(result, platform_success=False)

    assert not await kia_uvo.async_unload_entry(hass, entry)

    stop_polling.assert_not_awaited()
    close.assert_not_called()
    assert entry.unique_id in hass.data[DOMAIN]


async def test_cleanup_failure_is_sanitized_and_does_not_block_unload(
    monkeypatch, caplog, stop_polling
):
    result = coordinator(
        SimpleNamespace(close=Mock(side_effect=RuntimeError("PRIVATE_ACCOUNT_DATA")))
    )
    hass, entry = unload_fixture(result)
    services = Mock()
    monkeypatch.setattr(kia_uvo, "async_unload_services", services)

    assert await kia_uvo.async_unload_entry(hass, entry)

    assert hass.data[DOMAIN] == {}
    assert "Unable to shut down vehicle connection (RuntimeError)" in caplog.text
    assert "PRIVATE_ACCOUNT_DATA" not in caplog.text
    services.assert_called_once_with(hass)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConfigEntryAuthFailed("auth"), ConfigEntryAuthFailed),
        (RuntimeError("offline"), ConfigEntryNotReady),
    ],
)
async def test_failed_first_refresh_cleans_up_and_preserves_auth_error(
    monkeypatch, stop_polling, error, expected
):
    close = Mock()
    result = coordinator(SimpleNamespace(close=close))
    result.async_config_entry_first_refresh = AsyncMock(side_effect=error)
    monkeypatch.setattr(
        kia_uvo, "HyundaiKiaConnectDataUpdateCoordinator", Mock(return_value=result)
    )

    with pytest.raises(expected) as info:
        await kia_uvo.async_setup_entry(Mock(), Mock())

    close.assert_called_once()
    if expected is ConfigEntryAuthFailed:
        assert info.value is error
    else:
        assert info.value.__cause__ is error


async def test_manager_cleanup_runs_even_when_polling_shutdown_fails(stop_polling):
    error = RuntimeError("polling shutdown")
    stop_polling.side_effect = error
    close = Mock()
    result = coordinator(SimpleNamespace(close=close))

    with pytest.raises(RuntimeError) as info:
        await result.async_shutdown()

    assert info.value is error
    close.assert_called_once()
