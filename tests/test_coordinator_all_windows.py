"""Tests for the coordinator's all-windows commands."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hyundai_kia_connect_api.const import WINDOW_STATE
import pytest

from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator


class _FakeHass:
    async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
        return func(*args)


@pytest.mark.parametrize(
    ("method", "state"),
    [
        ("async_open_all_windows", WINDOW_STATE.OPEN),
        ("async_close_all_windows", WINDOW_STATE.CLOSED),
        ("async_vent_all_windows", WINDOW_STATE.VENTILATION),
    ],
)
async def test_all_windows_sets_every_window_then_waits(
    method: str, state: WINDOW_STATE
) -> None:
    coordinator = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    coordinator.hass = _FakeHass()  # type: ignore[assignment]
    coordinator._action_lock = asyncio.Lock()
    coordinator.vehicle_manager = MagicMock()
    coordinator.vehicle_manager.set_windows_state.return_value = "action-1"
    coordinator.async_check_and_refresh_token = AsyncMock()  # type: ignore[method-assign]
    coordinator.async_refresh = AsyncMock()  # type: ignore[method-assign]

    with patch("asyncio.sleep", AsyncMock()):
        await getattr(coordinator, method)("v1")

    vehicle_id, options = coordinator.vehicle_manager.set_windows_state.call_args.args
    assert vehicle_id == "v1"
    assert (
        options.front_left,
        options.front_right,
        options.back_left,
        options.back_right,
    ) == (state, state, state, state)
    coordinator.vehicle_manager.check_action_status.assert_called_once_with(
        "v1", "action-1", True, 60
    )
    coordinator.async_refresh.assert_awaited_once()
