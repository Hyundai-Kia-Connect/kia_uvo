"""Unload releases optional region API network sessions outside the event loop."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError
from test_region_operation_serialization import coordinator

from custom_components.kia_uvo import async_unload_entry
from custom_components.kia_uvo.const import DOMAIN


async def test_non_japan_unload_does_not_add_adapter_close_behavior(monkeypatch):
    close = Mock()
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "synthetic": SimpleNamespace(
                    vehicle_manager=SimpleNamespace(api=SimpleNamespace(close=close))
                )
            }
        },
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=True)
        ),
        async_add_executor_job=AsyncMock(),
    )
    monkeypatch.setattr("custom_components.kia_uvo.async_unload_services", Mock())
    assert await async_unload_entry(hass, SimpleNamespace(unique_id="synthetic"))
    hass.async_add_executor_job.assert_not_awaited()
    close.assert_not_called()
    assert hass.data[DOMAIN] == {}


async def test_old_region_without_close_unloads_unchanged(monkeypatch):
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "synthetic": SimpleNamespace(
                    vehicle_manager=SimpleNamespace(api=SimpleNamespace())
                )
            }
        },
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=True)
        ),
        async_add_executor_job=AsyncMock(),
    )
    monkeypatch.setattr("custom_components.kia_uvo.async_unload_services", Mock())
    assert await async_unload_entry(hass, SimpleNamespace(unique_id="synthetic"))
    hass.async_add_executor_job.assert_not_awaited()


async def test_failed_platform_unload_keeps_api_session_open():
    close = Mock()
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "synthetic": SimpleNamespace(
                    vehicle_manager=SimpleNamespace(api=SimpleNamespace(close=close))
                )
            }
        },
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=False)
        ),
        async_add_executor_job=AsyncMock(),
    )
    assert not await async_unload_entry(hass, SimpleNamespace(unique_id="synthetic"))
    hass.async_add_executor_job.assert_not_awaited()
    assert "synthetic" in hass.data[DOMAIN]


async def test_non_japan_unload_ignores_shutdown_hook(monkeypatch):
    shutdown = AsyncMock()
    close = Mock()
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "synthetic": SimpleNamespace(
                    async_shutdown=shutdown,
                    vehicle_manager=SimpleNamespace(api=SimpleNamespace(close=close)),
                )
            }
        },
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=True)
        ),
        async_add_executor_job=AsyncMock(),
    )
    monkeypatch.setattr("custom_components.kia_uvo.async_unload_services", Mock())
    assert await async_unload_entry(hass, SimpleNamespace(unique_id="synthetic"))
    shutdown.assert_not_awaited()
    hass.async_add_executor_job.assert_not_awaited()
    close.assert_not_called()


async def test_failed_platform_unload_does_not_start_shutdown():
    shutdown = AsyncMock()
    close = Mock()
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "synthetic": SimpleNamespace(
                    async_shutdown=shutdown,
                    vehicle_manager=SimpleNamespace(api=SimpleNamespace(close=close)),
                )
            }
        },
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=False)
        ),
        async_add_executor_job=AsyncMock(),
    )
    assert not await async_unload_entry(hass, SimpleNamespace(unique_id="synthetic"))
    shutdown.assert_not_awaited()
    close.assert_not_called()
    assert "synthetic" in hass.data[DOMAIN]


async def test_unload_drains_existing_command_and_blocks_new_commands(monkeypatch):
    result = coordinator()
    result._closing = False
    result._async_unsub_refresh = Mock()
    result._async_unsub_shutdown = Mock()
    result._debounced_refresh = Mock()
    entered, finish = asyncio.Event(), asyncio.Event()
    close = Mock()
    result.vehicle_manager.api.close = close
    result.vehicle_manager.unlock = Mock(return_value="synthetic-action")

    async def executor(target, *args):
        return target(*args)

    async def confirmation(*args):
        entered.set()
        await finish.wait()

    result.hass.async_add_executor_job.side_effect = executor
    result.async_await_action_and_refresh = AsyncMock(side_effect=confirmation)
    result.hass.data = {DOMAIN: {"synthetic": result}}
    result.hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    monkeypatch.setattr("custom_components.kia_uvo.async_unload_services", Mock())
    command = asyncio.create_task(result.async_unlock_vehicle("synthetic"))
    await entered.wait()
    unloading = asyncio.create_task(
        async_unload_entry(result.hass, SimpleNamespace(unique_id="synthetic"))
    )
    try:
        # Shutdown marks closing before waiting for the operation lock.
        for _ in range(20):
            if result._closing:
                break
            await asyncio.sleep(0)
        assert result._closing
        assert not unloading.done()
        close.assert_not_called()
        with pytest.raises(HomeAssistantError, match="shutting down"):
            await result.async_lock_vehicle("synthetic")
    finally:
        finish.set()
        outcomes = await asyncio.gather(command, unloading, return_exceptions=True)
    assert outcomes == [None, True]
    close.assert_called_once_with()
    assert result._shutdown_requested is True
    result._async_unsub_refresh.assert_called_once_with()
    result._async_unsub_shutdown.assert_called_once_with()
    result._debounced_refresh.async_shutdown.assert_called_once_with()
    result.vehicle_manager.lock.assert_not_called()
    assert result.hass.data[DOMAIN] == {}
