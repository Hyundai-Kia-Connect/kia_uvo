"""Config flow for Hyundai / Kia Connect integration."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from hyundai_kia_connect_api import VehicleManager, Token
from hyundai_kia_connect_api.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    BRANDS,
    CONF_BRAND,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_NO_FORCE_REFRESH_HOUR_FINISH,
    CONF_NO_FORCE_REFRESH_HOUR_START,
    DEFAULT_FORCE_REFRESH_INTERVAL,
    DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH,
    DEFAULT_NO_FORCE_REFRESH_HOUR_START,
    DEFAULT_PIN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    CONF_RMTOKEN,
    CONF_DEVICE_ID,
    REGIONS,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
    DEFAULT_ENABLE_GEOLOCATION_ENTITY,
    DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
    REGION_EUROPE,
    REGION_USA,
    BRAND_HYUNDAI,
    BRAND_KIA,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PIN, default=DEFAULT_PIN): str,
        vol.Required(CONF_REGION): vol.In(REGIONS),
        vol.Required(CONF_BRAND): vol.In(BRANDS),
    }
)

STEP_REGION_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION): vol.In(REGIONS),
        vol.Required(CONF_BRAND): vol.In(BRANDS),
    }
)

STEP_CREDENTIALS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PIN, default=DEFAULT_PIN): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=15, max=999)
        ),
        vol.Required(
            CONF_FORCE_REFRESH_INTERVAL,
            default=DEFAULT_FORCE_REFRESH_INTERVAL,
        ): vol.All(vol.Coerce(int), vol.Range(min=90, max=9999)),
        vol.Required(
            CONF_NO_FORCE_REFRESH_HOUR_START,
            default=DEFAULT_NO_FORCE_REFRESH_HOUR_START,
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Required(
            CONF_NO_FORCE_REFRESH_HOUR_FINISH,
            default=DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH,
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Optional(
            CONF_ENABLE_GEOLOCATION_ENTITY,
            default=DEFAULT_ENABLE_GEOLOCATION_ENTITY,
        ): bool,
        vol.Optional(
            CONF_USE_EMAIL_WITH_GEOCODE_API,
            default=DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
        ): bool,
    }
)


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> Token:
    """Validate the user input allows us to connect."""
    try:
        api = VehicleManager.get_implementation_by_region_brand(
            user_input[CONF_REGION],
            user_input[CONF_BRAND],
            language=hass.config.language,
        )
        token: Token = await hass.async_add_executor_job(
            api.login, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )

        if token is None:
            raise InvalidAuth

        return token
    except AuthenticationError as err:
        raise InvalidAuth from err


class HyundaiKiaConnectOptionFlowHandler(config_entries.OptionsFlow):
    """Handle an option flow for Hyundai / Kia Connect."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options init setup."""

        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hyundai / Kia Connect."""

    VERSION = 2
    reauth_entry: ConfigEntry | None = None

    def __init__(self):
        """Initialize the config flow."""
        self._region_data = None
        self._pending_config: dict[str, Any] | None = None
        self._otp_notify_type: str = "EMAIL"
        self._api = None
        self._otp_ctx: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Initiate options flow instance."""
        return HyundaiKiaConnectOptionFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step for region/brand selection."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_REGION_DATA_SCHEMA
            )

        self._region_data = user_input
        self._region_data = user_input
        if REGIONS[self._region_data[CONF_REGION]] == REGION_EUROPE and (
            BRANDS[self._region_data[CONF_BRAND]] == BRAND_KIA
            or BRANDS[self._region_data[CONF_BRAND]] == BRAND_HYUNDAI
        ):
            return await self.async_step_credentials_token()
        return await self.async_step_credentials_password()

    async def async_step_credentials_password(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the credentials step."""
        errors = {}
        if user_input is not None:
            full_config = {**self._region_data, **user_input}
            try:
                if REGIONS[self._region_data[CONF_REGION]] == REGION_USA:
                    self._pending_config = full_config
                    return await self.async_step_send_otp()
                token: Token = await validate_input(self.hass, full_config)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.reauth_entry is None:
                    title = f"{BRANDS[self._region_data[CONF_BRAND]]} {REGIONS[self._region_data[CONF_REGION]]} {user_input[CONF_USERNAME]}"
                    await self.async_set_unique_id(
                        hashlib.sha256(title.encode("utf-8")).hexdigest()
                    )
                    self._abort_if_unique_id_configured()
                    data = {
                        **full_config,
                        CONF_RMTOKEN: getattr(token, "refresh_token", None),
                        CONF_DEVICE_ID: getattr(token, "device_id", None),
                    }
                    return self.async_create_entry(title=title, data=data)
                else:
                    data = {
                        **full_config,
                        CONF_RMTOKEN: getattr(token, "refresh_token", None),
                        CONF_DEVICE_ID: getattr(token, "device_id", None),
                    }
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data=data
                    )
                    await self.hass.config_entries.async_reload(
                        self.reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="credentials_password",
            data_schema=STEP_CREDENTIALS_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_credentials_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the credentials step."""
        errors = {}
        if user_input is not None:
            full_config = {**self._region_data, **user_input}
            try:
                token: Token = await validate_input(self.hass, full_config)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = {
                    **full_config,
                    CONF_RMTOKEN: getattr(token, "refresh_token", None),
                    CONF_DEVICE_ID: getattr(token, "device_id", None),
                }
                if self.reauth_entry is None:
                    title = f"{BRANDS[self._region_data[CONF_BRAND]]} {REGIONS[self._region_data[CONF_REGION]]} {user_input[CONF_USERNAME]}"
                    await self.async_set_unique_id(
                        hashlib.sha256(title.encode("utf-8")).hexdigest()
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=title, data=data)
                else:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data=data
                    )
                    await self.hass.config_entries.async_reload(
                        self.reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="credentials_token",
            data_schema=STEP_CREDENTIALS_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_send_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Send OTP to selected destination for USA region.

        Parameters
        ----------
        user_input : dict[str, Any] | None
            Form submission captured by the step, or None to render the form.

        Returns
        -------
        FlowResult
            The next step in the flow or a created entry.
        """
        errors = {}
        schema = vol.Schema(
            {vol.Required("notify_type", default="EMAIL"): vol.In(["EMAIL", "PHONE"])}
        )
        if user_input is None:
            return self.async_show_form(
                step_id="send_otp", data_schema=schema, errors=errors
            )
        self._otp_notify_type = str(user_input["notify_type"]).upper()
        cfg = self._pending_config
        try:
            if self._api is None:
                self._api = VehicleManager.get_implementation_by_region_brand(
                    cfg[CONF_REGION],
                    cfg[CONF_BRAND],
                    language=self.hass.config.language,
                )
            token, ctx = await self.hass.async_add_executor_job(
                self._api.start_login, cfg[CONF_USERNAME], cfg[CONF_PASSWORD]
            )
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception during start_login")
            errors["base"] = "unknown"
        else:
            if token is not None:
                data = {
                    **cfg,
                    CONF_RMTOKEN: getattr(token, "refresh_token", None),
                    CONF_DEVICE_ID: getattr(token, "device_id", None),
                }
                if self.reauth_entry is None:
                    title = f"{BRANDS[self._region_data[CONF_BRAND]]} {REGIONS[self._region_data[CONF_REGION]]} {cfg[CONF_USERNAME]}"
                    await self.async_set_unique_id(
                        hashlib.sha256(title.encode("utf-8")).hexdigest()
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=title, data=data)
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=data
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            self._otp_ctx = ctx or {}
            try:
                await self.hass.async_add_executor_job(
                    self._api.send_otp,
                    self._otp_ctx.get("otpKey"),
                    self._otp_notify_type,
                    self._otp_ctx.get("xid", ""),
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during send_otp")
                errors["base"] = "unknown"
            else:
                return await self.async_step_input_otp_code()
        return self.async_show_form(
            step_id="send_otp", data_schema=schema, errors=errors
        )

    def _login_send_otp(self, cfg: dict[str, Any], notify_type: str) -> Token | None:
        """Call login to send OTP and stop before code verification.

        Parameters
        ----------
        cfg : dict[str, Any]
            Combined configuration containing region, brand, username, and password.
        notify_type : str
            Destination for OTP delivery, either 'EMAIL' or 'PHONE'.

        Returns
        -------
        Token | None
            Token if login succeeded without OTP (rmtoken reuse), otherwise None.
        """
        api = VehicleManager.get_implementation_by_region_brand(
            cfg[CONF_REGION], cfg[CONF_BRAND], language=self.hass.config.language
        )

        def handler(ctx: dict) -> dict:
            if ctx.get("stage") == "choose_destination":
                return {"notify_type": notify_type}
            if ctx.get("stage") == "input_code":
                return {"otp_code": ""}
            return {}

        try:
            return api.login(
                cfg[CONF_USERNAME], cfg[CONF_PASSWORD], otp_handler=handler
            )
        except AuthenticationError:
            return None

    async def async_step_input_otp_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect OTP code from user and complete login.

        Parameters
        ----------
        user_input : dict[str, Any] | None
            Form submission containing the `otp_code`, or None to render the form.

        Returns
        -------
        FlowResult
            The next step in the flow or a created entry.
        """
        errors = {}
        schema = vol.Schema({vol.Required("otp_code"): str})
        if user_input is None:
            return self.async_show_form(
                step_id="input_otp_code", data_schema=schema, errors=errors
            )
        cfg = self._pending_config
        if self._api is None:
            self._api = VehicleManager.get_implementation_by_region_brand(
                cfg[CONF_REGION], cfg[CONF_BRAND], language=self.hass.config.language
            )
        try:
            token: Token = await self.hass.async_add_executor_job(
                self._api.verify_otp_and_complete_login,
                cfg[CONF_USERNAME],
                cfg[CONF_PASSWORD],
                self._otp_ctx.get("otpKey"),
                self._otp_ctx.get("xid", ""),
                user_input["otp_code"],
            )
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except AuthenticationError as err:
            msg = str(err)
            if "otp" in msg.lower():
                errors["base"] = "invalid_otp"
            else:
                errors["base"] = "invalid_auth"
        except Exception as err:  # pylint: disable=broad-except
            msg = str(err)
            if "otp" in msg.lower():
                errors["base"] = "invalid_otp"
            else:
                _LOGGER.exception("Unexpected exception during OTP verify")
                errors["base"] = "unknown"
        else:
            data = {
                **cfg,
                CONF_RMTOKEN: getattr(token, "refresh_token", None),
                CONF_DEVICE_ID: getattr(token, "device_id", None),
            }
            if self.reauth_entry is None:
                title = f"{BRANDS[self._region_data[CONF_BRAND]]} {REGIONS[self._region_data[CONF_REGION]]} {cfg[CONF_USERNAME]}"
                await self.async_set_unique_id(
                    hashlib.sha256(title.encode("utf-8")).hexdigest()
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=data)
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="input_otp_code", data_schema=schema, errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        self._reauth_config = True
        return await self.async_step_user()


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
