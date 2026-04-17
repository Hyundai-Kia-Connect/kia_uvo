"""Coordinator for Hyundai / Kia Connect integration."""

from __future__ import annotations

from datetime import timedelta
import traceback
import logging
import asyncio

from hyundai_kia_connect_api import (
    VehicleManager,
    ClimateRequestOptions,
    WindowRequestOptions,
    ScheduleChargingClimateRequestOptions,
    Token,
)
from hyundai_kia_connect_api.ApiImpl import OTPRequest
from hyundai_kia_connect_api.exceptions import AuthenticationError

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BRAND,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_NO_FORCE_REFRESH_HOUR_FINISH,
    CONF_NO_FORCE_REFRESH_HOUR_START,
    DEFAULT_FORCE_REFRESH_INTERVAL,
    DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH,
    DEFAULT_NO_FORCE_REFRESH_HOUR_START,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DEFAULT_ENABLE_GEOLOCATION_ENTITY,
    DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_TOKEN,
    REGIONS,
    REGION_USA,
)

_LOGGER = logging.getLogger(__name__)

AUTH_RETRY_DELAYS = (30 * 60, 6 * 60 * 60)
AUTH_FAILURE_INVALID = "invalid"
AUTH_FAILURE_TRANSIENT = "transient"
AUTH_FAILURE_UNKNOWN = "unknown"


class HyundaiKiaConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.platforms: set[str] = set()
        self.config_entry = config_entry
        self._auth_retry_attempt = 0

        self.vehicle_manager = VehicleManager(
            region=config_entry.data.get(CONF_REGION),
            brand=config_entry.data.get(CONF_BRAND),
            username=config_entry.data.get(CONF_USERNAME),
            password=config_entry.data.get(CONF_PASSWORD),
            pin=config_entry.data.get(CONF_PIN),
            geocode_api_enable=config_entry.options.get(
                CONF_ENABLE_GEOLOCATION_ENTITY, DEFAULT_ENABLE_GEOLOCATION_ENTITY
            ),
            geocode_api_use_email=config_entry.options.get(
                CONF_USE_EMAIL_WITH_GEOCODE_API, DEFAULT_USE_EMAIL_WITH_GEOCODE_API
            ),
            language=hass.config.language,
            token=Token.from_dict(config_entry.data.get(CONF_TOKEN, None))
            if config_entry.data.get(CONF_TOKEN, None)
            else None,
        )
        self.scan_interval: int = (
            config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL) * 60
        )
        self.force_refresh_interval: int = (
            config_entry.options.get(
                CONF_FORCE_REFRESH_INTERVAL, DEFAULT_FORCE_REFRESH_INTERVAL
            )
            * 60
        )
        self.no_force_refresh_hour_start: int = config_entry.options.get(
            CONF_NO_FORCE_REFRESH_HOUR_START, DEFAULT_NO_FORCE_REFRESH_HOUR_START
        )
        self.no_force_refresh_hour_finish: int = config_entry.options.get(
            CONF_NO_FORCE_REFRESH_HOUR_FINISH, DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH
        )
        self.enable_geolocation_entity = config_entry.options.get(
            CONF_ENABLE_GEOLOCATION_ENTITY, DEFAULT_ENABLE_GEOLOCATION_ENTITY
        )
        self.use_email_with_geocode_api = config_entry.options.get(
            CONF_USE_EMAIL_WITH_GEOCODE_API, DEFAULT_USE_EMAIL_WITH_GEOCODE_API
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=min(self.scan_interval, self.force_refresh_interval)
            ),
        )

    async def _async_update_data(self):
        """Update data via library. Called by update_coordinator periodically.

        Allow to update for the first time without further checking
        Allow force update, if time diff between latest update and `now` is greater than force refresh delta
        """
        try:
            await self.async_check_and_refresh_token()
        except UpdateFailed:
            raise
        except AuthenticationError as AuthError:
            raise ConfigEntryAuthFailed(AuthError) from AuthError
        except Exception as err:
            # Transient API errors (e.g. DeviceIDError, ReadTimeoutError) from
            # Kia's EU backend must be surfaced as UpdateFailed rather than
            # propagating as unexpected exceptions.  HA's update coordinator
            # counts unexpected exceptions and cancels the config entry after
            # enough consecutive failures, which makes all entities permanently
            # unavailable until the integration is manually reloaded.
            # Raising UpdateFailed(retry_after=60) keeps entities temporarily
            # unavailable and schedules an automatic retry after 60 seconds
            # instead of waiting for the next full poll interval.
            # See: https://github.com/Hyundai-Kia-Connect/kia_uvo/issues/1538
            raise UpdateFailed(
                f"Token refresh failed, will retry in 60s: {err}",
                retry_after=60,
            ) from err
        current_hour = dt_util.now().hour

        if (
            (self.no_force_refresh_hour_start <= self.no_force_refresh_hour_finish)
            and (
                current_hour < self.no_force_refresh_hour_start
                or current_hour >= self.no_force_refresh_hour_finish
            )
        ) or (
            (self.no_force_refresh_hour_start >= self.no_force_refresh_hour_finish)
            and (
                current_hour < self.no_force_refresh_hour_start
                and current_hour >= self.no_force_refresh_hour_finish
            )
        ):
            try:
                await self.hass.async_add_executor_job(
                    self.vehicle_manager.check_and_force_update_vehicles,
                    self.force_refresh_interval,
                )
            except Exception:
                try:
                    _LOGGER.exception(
                        f"Force update failed, falling back to cached: {traceback.format_exc()}"
                    )
                    await self.hass.async_add_executor_job(
                        self.vehicle_manager.update_all_vehicles_with_cached_state
                    )
                except Exception:
                    _LOGGER.exception(f"Cached update failed: {traceback.format_exc()}")
                    raise UpdateFailed(
                        f"Error communicating with API: {traceback.format_exc()}"
                    )

        else:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.update_all_vehicles_with_cached_state
            )

        return self.data

    async def async_update_all(self) -> None:
        """Update vehicle data."""
        await self.async_check_and_refresh_token()
        await self.hass.async_add_executor_job(
            self.vehicle_manager.update_all_vehicles_with_cached_state
        )
        await self.async_refresh()

    async def async_force_update_all(self) -> None:
        """Force refresh vehicle data and update it."""
        await self.async_check_and_refresh_token()
        await self.hass.async_add_executor_job(
            self.vehicle_manager.force_refresh_all_vehicles_states
        )
        await self.async_refresh()

    async def async_force_refresh_vehicle(self, vehicle_id: str) -> None:
        """Force refresh a single vehicle's state."""
        await self.async_check_and_refresh_token()
        await self.hass.async_add_executor_job(
            self.vehicle_manager.force_refresh_vehicle_state, vehicle_id
        )
        self.async_set_updated_data(self.data)

    async def async_check_and_refresh_token(self):
        """Refresh token if needed via library."""
        try:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.check_and_refresh_token
            )
        except AuthenticationError as err:
            await self._async_handle_auth_failure(err)
        self._reset_auth_retry_state()
        await self._async_save_token()

    async def _async_handle_auth_failure(self, err: AuthenticationError) -> None:
        """Classify auth failures before deciding whether to reauth or retry later."""
        failure_type = self._classify_auth_error(err)

        if failure_type == AUTH_FAILURE_TRANSIENT:
            raise self._build_auth_retry_error(err) from err

        if not self._should_try_silent_relogin():
            raise err

        _LOGGER.info(
            "Token refresh failed for Hyundai/Genesis USA account; attempting silent re-login"
        )

        try:
            result = await self.hass.async_add_executor_job(self.vehicle_manager.login)
        except AuthenticationError as login_err:
            failure_type = self._classify_auth_error(login_err)
            if failure_type == AUTH_FAILURE_TRANSIENT:
                raise self._build_auth_retry_error(login_err) from login_err
            raise login_err

        if result is None or isinstance(result, OTPRequest):
            raise err

    def _classify_auth_error(self, err: AuthenticationError) -> str:
        """Best-effort classification for auth failures."""
        message = str(err).lower()

        invalid_markers = (
            "invalid credential",
            "invalid_credentials",
            "invalid login",
            "wrong password",
            "incorrect password",
            "incorrect username",
            "invalid username",
            "unauthorized",
            "forbidden",
            "login failed: invalid",
        )
        transient_markers = (
            "maintenance",
            "undergoing planned",
            "temporarily unavailable",
            "service unavailable",
            "systems are currently",
            "try again later",
            "server error",
            "gateway timeout",
            "bad gateway",
            "too many requests",
            "rate limit",
        )

        if any(marker in message for marker in invalid_markers):
            return AUTH_FAILURE_INVALID
        if any(marker in message for marker in transient_markers):
            return AUTH_FAILURE_TRANSIENT
        return AUTH_FAILURE_UNKNOWN

    def _build_auth_retry_error(self, err: AuthenticationError) -> UpdateFailed:
        """Build a staged retry for transient auth failures."""
        delay = AUTH_RETRY_DELAYS[
            min(self._auth_retry_attempt, len(AUTH_RETRY_DELAYS) - 1)
        ]
        self._auth_retry_attempt += 1
        _LOGGER.warning(
            "Authentication temporarily failed while fetching %s data; retrying in %s seconds: %s",
            DOMAIN,
            delay,
            err,
        )
        return UpdateFailed(
            f"Authentication temporarily failed, will retry in {delay}s: {err}",
            retry_after=delay,
        )

    def _reset_auth_retry_state(self) -> None:
        """Clear auth retry backoff after a successful refresh/login."""
        self._auth_retry_attempt = 0

    def _should_try_silent_relogin(self) -> bool:
        """Only retry automatically for USA entries with stored credentials."""
        region = REGIONS.get(self.config_entry.data.get(CONF_REGION))

        return (
            region == REGION_USA
            and bool(self.config_entry.data.get(CONF_USERNAME))
            and bool(self.config_entry.data.get(CONF_PASSWORD))
        )

    async def async_await_action_and_refresh(self, vehicle_id, action_id):
        try:
            await asyncio.sleep(5)
            await self.hass.async_add_executor_job(
                self.vehicle_manager.check_action_status,
                vehicle_id,
                action_id,
                True,
                60,
            )
        finally:
            await self.async_refresh()

    async def async_await_action_and_force_refresh(self, vehicle_id, action_id):
        """Wait for action then force refresh to get fresh vehicle data.

        Used after setting charge limits because the soft refresh (cmm/gvi)
        does not return targetSOC for some vehicles. A force refresh (rems/rvs)
        ensures the fresh charge limits are read back immediately.

        Uses async_set_updated_data instead of async_refresh to avoid a
        redundant cmm/gvi API call — the force refresh already updates the
        vehicle objects in-place (rems/rvs + cmm/gvi), so we just need to
        notify HA entities to re-read their state.
        """
        try:
            await asyncio.sleep(5)
            await self.hass.async_add_executor_job(
                self.vehicle_manager.check_action_status,
                vehicle_id,
                action_id,
                True,
                60,
            )
        finally:
            try:
                await self.hass.async_add_executor_job(
                    self.vehicle_manager.force_refresh_vehicle_state, vehicle_id
                )
            except Exception:
                _LOGGER.exception("Force refresh after setting charge limits failed")
            self.async_set_updated_data(self.data)

    async def async_lock_vehicle(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.lock, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to lock vehicle: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_unlock_vehicle(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.unlock, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to unlock vehicle: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_open_charge_port(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.open_charge_port, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to open charge port: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_close_charge_port(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.close_charge_port, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to close charge port: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_climate_default(self, vehicle_id: str):
        """Start climate with default options (API fills sensible defaults)."""
        await self.async_start_climate(vehicle_id, ClimateRequestOptions())

    async def async_start_climate(
        self, vehicle_id: str, climate_options: ClimateRequestOptions
    ):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.start_climate, vehicle_id, climate_options
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to start climate: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_stop_climate(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.stop_climate, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to stop climate: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_charge(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.start_charge, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to start charge: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_stop_charge(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.stop_charge, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to stop charge: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_set_charge_limits(self, vehicle_id: str, ac: int, dc: int):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.set_charge_limits, vehicle_id, ac, dc
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set charge limits: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_force_refresh(vehicle_id, action_id)
        )

    async def async_set_charging_current(self, vehicle_id: str, level: int):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.set_charging_current, vehicle_id, level
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set charging current: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_schedule_charging_and_climate(
        self, vehicle_id: str, schedule_options: ScheduleChargingClimateRequestOptions
    ):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.schedule_charging_and_climate,
                vehicle_id,
                schedule_options,
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to schedule charging and climate: {err}"
            ) from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_hazard_lights(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.start_hazard_lights, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to start hazard lights: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_hazard_lights_and_horn(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.start_hazard_lights_and_horn,
                vehicle_id,
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to start hazard lights and horn: {err}"
            ) from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_valet_mode(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.start_valet_mode, vehicle_id
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to start valet mode: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_stop_valet_mode(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.stop_valet_mode,
                vehicle_id,
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to stop valet mode: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_set_v2l_limit(self, vehicle_id: str, limit: int):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.set_vehicle_to_load_discharge_limit,
                vehicle_id,
                limit,
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set V2L limit: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_set_windows(
        self, vehicle_id: str, windowOptions: WindowRequestOptions
    ):
        await self.async_check_and_refresh_token()
        try:
            action_id = await self.hass.async_add_executor_job(
                self.vehicle_manager.set_windows_state, vehicle_id, windowOptions
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set windows: {err}") from err
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def _async_save_token(self):
        """Persist the latest token into the config entry."""
        new_token = self.vehicle_manager.token.to_dict()
        # Only update if token actually changed
        if new_token and new_token != self.config_entry.data.get(CONF_TOKEN):
            updated_data = {**self.config_entry.data, CONF_TOKEN: new_token}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=updated_data
            )
