"""Tests for the EU 20-character password truncation hint (#1979)."""

from unittest.mock import MagicMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_REGION
import pytest

from custom_components.kia_uvo.config_flow import (
    ConfigFlow,
    InvalidAuth,
    _auth_error_base,
)


def test_auth_error_base_hint_on_eu_long_password():
    long_password = "x" * 21
    assert _auth_error_base({CONF_REGION: 1, CONF_PASSWORD: long_password}) == (
        "password_truncated_hint"
    )
    assert _auth_error_base({CONF_REGION: 9, CONF_PASSWORD: long_password}) == (
        "password_truncated_hint"
    )


def test_auth_error_base_stays_invalid_auth_otherwise():
    short_password = "x" * 20
    assert _auth_error_base({CONF_REGION: 1, CONF_PASSWORD: short_password}) == (
        "invalid_auth"
    )
    long_password = "x" * 21
    assert _auth_error_base({CONF_REGION: 2, CONF_PASSWORD: long_password}) == (
        "invalid_auth"
    )


@pytest.mark.asyncio
async def test_credentials_step_uses_hint_base_on_eu_long_password():
    """The password step replaces invalid_auth with the hint key on EU+>20."""
    flow = ConfigFlow.__new__(ConfigFlow)
    flow.hass = MagicMock()
    flow._region_data = {
        CONF_REGION: 1,
        "brand": 2,
        "username": "u",
        CONF_PASSWORD: "current",
        "pin": None,
    }
    flow._is_reconfigure = False
    flow._otp_request = None
    flow.reauth_entry = None

    with (
        patch("custom_components.kia_uvo.config_flow.VehicleManager"),
        patch(
            "custom_components.kia_uvo.config_flow.validate_input",
            side_effect=InvalidAuth,
        ),
        patch.object(ConfigFlow, "async_show_form", return_value="form") as show,
    ):
        await flow.async_step_credentials_password(
            {
                "username": "u",
                "password": "x" * 24,
                "pin": None,
            }
        )

    show.assert_called_once()
    assert show.call_args.kwargs["errors"].get("base") == "password_truncated_hint"
