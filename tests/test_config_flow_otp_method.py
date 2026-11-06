"""Tests for the config flow's OTP method selection step."""

from unittest.mock import MagicMock, patch

from hyundai_kia_connect_api.const import OTP_NOTIFY_TYPE
import pytest

from custom_components.kia_uvo.config_flow import ConfigFlow


@pytest.mark.parametrize(
    ("choice", "expected"),
    [("EMAIL", OTP_NOTIFY_TYPE.EMAIL), ("SMS", OTP_NOTIFY_TYPE.SMS)],
)
@pytest.mark.asyncio
async def test_select_otp_method_sends_chosen_method(
    choice: str, expected: OTP_NOTIFY_TYPE
) -> None:
    flow = ConfigFlow.__new__(ConfigFlow)
    flow.hass = MagicMock()
    sent: list[OTP_NOTIFY_TYPE] = []

    async def run(func, *args):
        sent.extend(args)
        return func(*args)

    flow.hass.async_add_executor_job = run
    flow._vehicle_manager = MagicMock()

    with patch.object(ConfigFlow, "async_step_enter_otp", return_value="otp"):
        result = await flow.async_step_select_otp_method({"method": choice})

    assert result == "otp"
    assert sent == [expected]
    flow._vehicle_manager.send_otp.assert_called_once_with(expected)
