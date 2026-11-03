"""Japan is Hyundai-only and uses the shared credential flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import CONF_REGION

from custom_components.kia_uvo.config_flow import ConfigFlow
from custom_components.kia_uvo.const import CONF_BRAND, REGIONS


@pytest.mark.parametrize("brand", ["1", "3"])
async def test_japan_rejects_unsupported_brand_before_login(brand: str) -> None:
    flow = ConfigFlow()
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    flow.async_step_credentials_password = AsyncMock()
    await flow.async_step_user({CONF_REGION: "10", CONF_BRAND: brand})
    assert flow.async_show_form.call_args.kwargs["errors"] == {
        CONF_BRAND: "unsupported_japan_brand"
    }
    flow.async_step_credentials_password.assert_not_awaited()


async def test_japan_hyundai_enters_shared_password_flow() -> None:
    flow = ConfigFlow()
    flow.async_step_credentials_password = AsyncMock()
    await flow.async_step_user({CONF_REGION: "10", CONF_BRAND: "2"})
    assert flow._region_data == {CONF_REGION: 10, CONF_BRAND: 2}
    flow.async_step_credentials_password.assert_awaited_once_with()
    assert REGIONS[10] == "Japan"


async def test_existing_region_keeps_all_brand_choices() -> None:
    flow = ConfigFlow()
    flow.async_step_credentials_password = AsyncMock()
    await flow.async_step_user({CONF_REGION: "1", CONF_BRAND: "1"})
    flow.async_step_credentials_password.assert_awaited_once_with()


async def test_japan_login_builds_manager_and_creates_entry(monkeypatch) -> None:
    from custom_components.kia_uvo import config_flow

    flow = ConfigFlow()
    flow._region_data = {CONF_REGION: 10, CONF_BRAND: 2}
    flow.hass = MagicMock()
    flow.hass.config.language = "ja"
    flow.hass.async_add_executor_job = AsyncMock(return_value=config_flow.Token())
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    constructor = MagicMock()
    monkeypatch.setattr(config_flow, "VehicleManager", constructor)
    result = await flow.async_step_credentials_password(
        {"username": "synthetic", "password": "synthetic", "pin": "synthetic-pin"}
    )
    assert result["type"] == "create_entry"
    assert constructor.call_args.kwargs["region"] == 10
    assert constructor.call_args.kwargs["brand"] == 2
    assert (
        flow.async_create_entry.call_args.kwargs["title"] == "Hyundai Japan synthetic"
    )


async def test_japan_invalid_auth_stays_on_credentials_form(monkeypatch) -> None:
    from custom_components.kia_uvo import config_flow

    flow = ConfigFlow()
    flow._region_data = {CONF_REGION: 10, CONF_BRAND: 2}
    flow.hass = MagicMock()
    flow.hass.async_add_executor_job = AsyncMock(
        side_effect=config_flow.AuthenticationError("synthetic failure")
    )
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    monkeypatch.setattr(config_flow, "VehicleManager", MagicMock())
    await flow.async_step_credentials_password(
        {"username": "synthetic", "password": "synthetic", "pin": "synthetic-pin"}
    )
    assert flow.async_show_form.call_args.kwargs["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize("step", ["credentials_password", "credentials_token"])
@pytest.mark.parametrize("pin", [None, "", "   ", 1234])
async def test_japan_missing_pin_rejected_before_login(monkeypatch, step, pin):
    from custom_components.kia_uvo import config_flow

    flow = ConfigFlow()
    flow._region_data = {CONF_REGION: 10, CONF_BRAND: 2}
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    constructor = MagicMock()
    monkeypatch.setattr(config_flow, "VehicleManager", constructor)
    supplied = {"username": "synthetic", "password": "synthetic"}
    if pin is not None:
        supplied["pin"] = pin
    await getattr(flow, "async_step_" + step)(supplied)
    assert flow.async_show_form.call_args.kwargs["errors"] == {
        "pin": "invalid_japan_pin"
    }
    constructor.assert_not_called()


async def test_japan_schema_has_required_pin_without_default():
    import voluptuous as vol

    from custom_components.kia_uvo.config_flow import STEP_JAPAN_CREDENTIALS_DATA_SCHEMA

    flow = ConfigFlow()
    flow._region_data = {CONF_REGION: 10, CONF_BRAND: 2}
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    await flow.async_step_credentials_password()
    schema = flow.async_show_form.call_args.kwargs["data_schema"]
    assert schema is STEP_JAPAN_CREDENTIALS_DATA_SCHEMA
    with pytest.raises(vol.MultipleInvalid):
        schema({"username": "synthetic", "password": "synthetic"})
    pin_marker = next(marker for marker in schema.schema if marker.schema == "pin")
    assert isinstance(pin_marker, vol.Required)
    assert pin_marker.default is vol.UNDEFINED


async def test_other_regions_keep_optional_pin_default():
    from custom_components.kia_uvo.config_flow import STEP_CREDENTIALS_DATA_SCHEMA
    from custom_components.kia_uvo.const import DEFAULT_PIN

    flow = ConfigFlow()
    flow._region_data = {CONF_REGION: 1, CONF_BRAND: 2}
    schema = flow._credentials_schema()
    assert schema is STEP_CREDENTIALS_DATA_SCHEMA
    assert (
        schema({"username": "synthetic", "password": "synthetic"})["pin"] == DEFAULT_PIN
    )


async def test_japan_reauth_uses_required_pin_schema():
    from custom_components.kia_uvo.config_flow import STEP_JAPAN_CREDENTIALS_DATA_SCHEMA

    flow = ConfigFlow()
    flow.reauth_entry = MagicMock()
    flow._region_data = {CONF_REGION: 10, CONF_BRAND: 2}
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    await flow.async_step_credentials_password()
    assert (
        flow.async_show_form.call_args.kwargs["data_schema"]
        is STEP_JAPAN_CREDENTIALS_DATA_SCHEMA
    )
