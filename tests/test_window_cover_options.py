"""Tests for the window cover's WindowRequestOptions."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.ApiImpl import WindowRequestOptions
from hyundai_kia_connect_api.const import WINDOW_STATE

from custom_components.kia_uvo.cover import (
    COVER_DESCRIPTIONS,
    HyundaiKiaConnectCover,
)


@pytest.mark.parametrize("description", COVER_DESCRIPTIONS, ids=lambda d: d.key)
@pytest.mark.asyncio
async def test_open_sets_only_this_window(description) -> None:
    coordinator = MagicMock()
    coordinator.async_set_windows = AsyncMock()
    vehicle = Vehicle(id="v1")
    cover = HyundaiKiaConnectCover(coordinator, description, vehicle)

    await cover.async_open_cover()

    coordinator.async_set_windows.assert_awaited_once_with(
        "v1",
        WindowRequestOptions(**{description.window_position: WINDOW_STATE.OPEN}),
    )
