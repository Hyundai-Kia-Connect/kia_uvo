"""Tests for the MyHyundai Korea browser-login flow."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_REGION, CONF_USERNAME
from hyundai_kia_connect_api import Token
from hyundai_kia_connect_api.exceptions import AuthenticationError

from custom_components.kia_uvo.binary_sensor import _seat_heater_is_on
from custom_components.kia_uvo.config_flow import ConfigFlow
from custom_components.kia_uvo.const import (
    CONF_BRAND,
    CONF_OAUTH_REDIRECT_URL,
    CONF_TOKEN,
    REGIONS,
)
from custom_components.kia_uvo.coordinator import _token_from_config
from custom_components.kia_uvo.services import _seat_climate_state


class FakeHass:
    """Small Home Assistant stub for executor-backed config-flow calls."""

    def __init__(self) -> None:
        self.config = SimpleNamespace(language="en")
        self.config_entries = MagicMock()

    async def async_add_executor_job(self, target, *args):
        """Run the blocking function inline for a deterministic test."""
        return target(*args)


class FakeVehicleManager:
    """VehicleManager stub that returns a renewable token set."""

    def __init__(self, **kwargs) -> None:
        self.init_args = kwargs
        self.token = Token(
            username="person@example.com",
            password="account-password",
            access_token="Bearer ccs-token",
            refresh_token="refresh-token",
            pin=kwargs["pin"],
            control_token="control-token",
            control_token_expiry=123,
            user_id="account-id",
        )
        self.vehicles = {"vehicle-id": MagicMock()}
        self.redirect_url: str | None = None

    def get_authorization_url(self) -> str:
        return "https://idpconnect-kr.hyundai.com/authorize"

    def login_with_redirect_url(self, redirect_url: str) -> bool:
        self.redirect_url = redirect_url
        return True


def _flow() -> ConfigFlow:
    flow = ConfigFlow()
    flow.hass = FakeHass()
    return flow


@pytest.mark.asyncio
async def test_korea_hyundai_routes_to_browser_login() -> None:
    flow = _flow()

    with patch(
        "custom_components.kia_uvo.config_flow.VehicleManager", FakeVehicleManager
    ):
        result = await flow.async_step_user({CONF_REGION: "10", CONF_BRAND: "2"})

    assert REGIONS[10] == "Korea"
    assert result["type"] == "form"
    assert result["step_id"] == "credentials_browser"
    assert result["description_placeholders"] == {
        "authorization_url": "https://idpconnect-kr.hyundai.com/authorize"
    }


def test_korea_login_instructions_select_pleos_account() -> None:
    """Tell users how to switch away from the legacy Hyundai login form."""
    strings_path = Path(__file__).parents[1] / "custom_components/kia_uvo/strings.json"
    description = json.loads(strings_path.read_text())["config"]["step"][
        "credentials_browser"
    ]["description"]

    assert "Pleos account login" in description


@pytest.mark.asyncio
async def test_korea_rejects_non_hyundai_brand() -> None:
    flow = _flow()

    result = await flow.async_step_user({CONF_REGION: "10", CONF_BRAND: "1"})

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unsupported_region_brand"}


@pytest.mark.asyncio
async def test_browser_login_stores_renewable_token_without_callback_or_secrets() -> (
    None
):
    flow = _flow()
    flow._region_data = {CONF_REGION: 10, CONF_BRAND: 2}
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    callback = "https://oneapp.hyundai.com/redirect?code=one-time-code&state=hmgoneapp"

    with patch(
        "custom_components.kia_uvo.config_flow.VehicleManager", FakeVehicleManager
    ):
        result = await flow.async_step_credentials_browser(
            {CONF_OAUTH_REDIRECT_URL: f"  {callback}  ", CONF_PIN: "1234"}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Hyundai Korea"
    data = result["data"]
    assert data[CONF_REGION] == 10
    assert data[CONF_BRAND] == 2
    assert data[CONF_USERNAME] == ""
    assert data[CONF_PASSWORD] == ""
    assert data[CONF_PIN] == "1234"
    assert CONF_OAUTH_REDIRECT_URL not in data
    assert data[CONF_TOKEN]["refresh_token"] == "refresh-token"
    assert data[CONF_TOKEN]["password"] is None
    assert data[CONF_TOKEN]["pin"] is None
    assert data[CONF_TOKEN]["control_token"] is None


@pytest.mark.asyncio
async def test_browser_login_reports_invalid_callback() -> None:
    class RejectingVehicleManager(FakeVehicleManager):
        def login_with_redirect_url(self, redirect_url: str) -> bool:
            raise AuthenticationError("invalid callback")

    flow = _flow()
    flow._region_data = {CONF_REGION: 10, CONF_BRAND: 2}

    with patch(
        "custom_components.kia_uvo.config_flow.VehicleManager",
        RejectingVehicleManager,
    ):
        result = await flow.async_step_credentials_browser(
            {CONF_OAUTH_REDIRECT_URL: "https://example.com", CONF_PIN: "1234"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "credentials_browser"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_korea_reauth_returns_directly_to_browser_login() -> None:
    flow = _flow()
    entry = MagicMock(
        entry_id="entry-id",
        data={CONF_REGION: 10, CONF_BRAND: 2},
    )
    flow.context = {"entry_id": "entry-id"}
    flow.hass.config_entries.async_get_entry.return_value = entry

    confirm = await flow.async_step_reauth()
    with patch(
        "custom_components.kia_uvo.config_flow.VehicleManager", FakeVehicleManager
    ):
        browser = await flow.async_step_reauth_confirm({})

    assert confirm["step_id"] == "reauth_confirm"
    assert browser["step_id"] == "credentials_browser"
    assert flow._region_data == {CONF_REGION: 10, CONF_BRAND: 2}


def test_config_token_round_trip_injects_pin_only_at_runtime() -> None:
    token = Token(
        access_token="Bearer ccs-token",
        refresh_token="refresh-token",
        pin="1234",
        control_token="short-lived-control-token",
        control_token_expiry=123,
    )

    stored = token.to_persistent_dict()
    restored = _token_from_config(stored, "5678")

    assert stored["refresh_token"] == "refresh-token"
    assert stored["pin"] is None
    assert stored["control_token"] is None
    assert restored is not None
    assert restored.refresh_token == "refresh-token"
    assert restored.pin == "5678"
    assert restored.control_token is None


def test_korea_seat_off_uses_gen2_off_state() -> None:
    assert _seat_climate_state("0", 10) == 2
    assert _seat_climate_state("6", 10) == 6
    assert _seat_climate_state("0", 1) == 0
    assert _seat_climate_state(None, 10) is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Off", False),
        ("Low Cool", False),
        ("High Cool", False),
        ("On", True),
        ("Low Heat", True),
        ("High Heat", True),
    ],
)
def test_seat_heater_binary_sensor_uses_status_meaning(
    status: str, expected: bool
) -> None:
    assert _seat_heater_is_on(status) is expected
