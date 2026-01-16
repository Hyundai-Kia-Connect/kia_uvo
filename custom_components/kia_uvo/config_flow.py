"""Config flow for Hyundai / Kia Connect integration."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from hyundai_kia_connect_api import Token, VehicleManager
from hyundai_kia_connect_api.ApiImpl import OTPRequest
from hyundai_kia_connect_api.exceptions import AuthenticationError
from hyundai_kia_connect_api.const import OTP_NOTIFY_TYPE

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
    CONF_TOKEN,
    DEFAULT_FORCE_REFRESH_INTERVAL,
    DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH,
    DEFAULT_NO_FORCE_REFRESH_HOUR_START,
    DEFAULT_PIN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REGIONS,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
    DEFAULT_ENABLE_GEOLOCATION_ENTITY,
    DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
    REGION_EUROPE,
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


async def validate_input(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    vehicle_manager: VehicleManager | None = None,
) -> Token | OTPRequest:
    """Validate the user input allows us to connect."""
    try:
        result = await hass.async_add_executor_job(vehicle_manager.login)

        if result is None:
            raise InvalidAuth

        return result
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
        self._vehicle_manager: VehicleManager | None = None
        self._pending_login_data = None
        self._otp_request: OTPRequest | None = None

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
            # Combine region data with credentials
            full_config = {**self._region_data, **user_input}
            self._vehicle_manager = VehicleManager(
                region=full_config[CONF_REGION],
                brand=full_config[CONF_BRAND],
                language=self.hass.config.language,
                username=full_config[CONF_USERNAME],
                password=full_config[CONF_PASSWORD],
                pin=full_config[CONF_PIN],
            )
            try:
                result = await validate_input(
                    self.hass, full_config, self._vehicle_manager
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if isinstance(result, OTPRequest):
                    self._pending_login_data = full_config
                    self._otp_request = result

                    return await self.async_step_select_otp_method()
                if self.reauth_entry is None:
                    title = f"{BRANDS[self._region_data[CONF_BRAND]]} {REGIONS[self._region_data[CONF_REGION]]} {user_input[CONF_USERNAME]}"
                    await self.async_set_unique_id(
                        hashlib.sha256(title.encode("utf-8")).hexdigest()
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=title, data=full_config)
                else:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data=full_config
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

    async def async_step_select_otp_method(self, user_input=None):
        """Let user choose email or SMS."""
        if user_input is None:
            # Add code to build a list of available OTP methods
            otp_methods = []
            if self._otp_request.has_email:
                otp_methods.append("EMAIL")
            if self._otp_request.has_sms:
                otp_methods.append("SMS")
            return self.async_show_form(
                step_id="select_otp_method",
                data_schema=vol.Schema({vol.Required("method"): vol.In(otp_methods)}),
            )
        if user_input["method"] == "EMAIL":
            method = OTP_NOTIFY_TYPE.EMAIL
        if user_input["method"] == "SMS":
            method = OTP_NOTIFY_TYPE.SMS
        await self.hass.async_add_executor_job(self._vehicle_manager.send_otp, method)

        return await self.async_step_enter_otp()

    async def async_step_enter_otp(self, user_input=None):
        """Prompt user to enter the OTP."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="enter_otp", data_schema=vol.Schema({vol.Required("otp"): str})
            )

        try:
            await self.hass.async_add_executor_job(
                self._vehicle_manager.verify_otp_and_complete_login,
                user_input["otp"],
            )
        except AuthenticationError:
            errors["base"] = "invalid_otp"
            return self.async_show_form(
                step_id="enter_otp",
                data_schema=vol.Schema({vol.Required("otp"): str}),
                errors=errors,
            )
        self._pending_login_data[CONF_TOKEN] = self._vehicle_manager.token.to_dict()
        if self.reauth_entry is None:
            title = f"{BRANDS[self._pending_login_data[CONF_BRAND]]} {REGIONS[self._pending_login_data[CONF_REGION]]} {self._pending_login_data[CONF_USERNAME]}"
            await self.async_set_unique_id(
                hashlib.sha256(title.encode("utf-8")).hexdigest()
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=title, data=self._pending_login_data)
        else:
            self.hass.config_entries.async_update_entry(
                self.reauth_entry, data=self._pending_login_data
            )
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

    async def async_step_credentials_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the credentials step."""
        errors = {}

        if user_input is not None:
            # Combine region data with credentials
            full_config = {**self._region_data, **user_input}
            self._vehicle_manager = VehicleManager(
                region=full_config[CONF_REGION],
                brand=full_config[CONF_BRAND],
                language=self.hass.config.language,
                username=full_config[CONF_USERNAME],
                password=full_config[CONF_PASSWORD],
                pin=full_config[CONF_PIN],
            )
            try:
                await validate_input(self.hass, full_config, self._vehicle_manager)
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
                    return self.async_create_entry(title=title, data=full_config)
                else:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data=full_config
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
