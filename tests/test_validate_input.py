"""Tests for config flow login validation."""

from unittest.mock import MagicMock

import pytest

from custom_components.kia_uvo.config_flow import InvalidAuth, validate_input


def _hass() -> MagicMock:
    hass = MagicMock()

    async def run(func):
        return func()

    hass.async_add_executor_job = run
    return hass


@pytest.mark.parametrize("result", [None, False])
@pytest.mark.asyncio
async def test_failed_login_raises_invalid_auth(result: bool | None) -> None:
    vehicle_manager = MagicMock()
    vehicle_manager.login.return_value = result
    with pytest.raises(InvalidAuth):
        await validate_input(_hass(), {}, vehicle_manager)


@pytest.mark.asyncio
async def test_successful_login_returns_result() -> None:
    vehicle_manager = MagicMock()
    vehicle_manager.login.return_value = True
    assert await validate_input(_hass(), {}, vehicle_manager) is True
