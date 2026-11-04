"""Tests for how async_setup_entry surfaces first-refresh failures."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import pytest

from custom_components.kia_uvo import async_setup_entry


def _patch_first_refresh(error: Exception) -> Any:
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=error)
    return patch(
        "custom_components.kia_uvo.HyundaiKiaConnectDataUpdateCoordinator",
        return_value=coordinator,
    )


@pytest.mark.asyncio
async def test_auth_failure_propagates_unchanged() -> None:
    error = ConfigEntryAuthFailed("bad credentials")
    with _patch_first_refresh(error), pytest.raises(ConfigEntryAuthFailed) as info:
        await async_setup_entry(MagicMock(), MagicMock())
    assert info.value is error


@pytest.mark.asyncio
async def test_other_failure_becomes_not_ready_with_cause() -> None:
    error = RuntimeError("vendor down")
    with _patch_first_refresh(error), pytest.raises(ConfigEntryNotReady) as info:
        await async_setup_entry(MagicMock(), MagicMock())
    assert info.value.__cause__ is error
