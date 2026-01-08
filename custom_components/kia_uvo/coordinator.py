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
)
from hyundai_kia_connect_api.exceptions import AuthenticationError

from homeassistant.exceptions import ConfigEntryAuthFailed

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
)

_LOGGER = logging.getLogger(__name__)


class HyundaiKiaConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.platforms: set[str] = set()
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
        )

        # Monkey patch to log API responses before they cause KeyError
        if hasattr(self.vehicle_manager, 'api') and hasattr(self.vehicle_manager.api, '_get_vehicle_status'):
            original_get_vehicle_status = self.vehicle_manager.api._get_vehicle_status

            def logged_get_vehicle_status(token, vehicle, force_refresh):
                """Wrapper to log API response before processing."""
                try:
                    # Call original method - it will make the HTTP request
                    # We can't intercept before the dict() call, so we'll catch the error
                    return original_get_vehicle_status(token, vehicle, force_refresh)
                except KeyError as err:
                    # Log what we can access from the response
                    _LOGGER.error(
                        "KeyError in _get_vehicle_status: %s. "
                        "This typically indicates Hyundai API returned an error response (rate limit/502). "
                        "Enable hyundai_kia_connect_api debug logging to see full HTTP response.",
                        err
                    )
                    raise

            self.vehicle_manager.api._get_vehicle_status = logged_get_vehicle_status
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

        # Circuit breaker for API rate limiting
        self._consecutive_failures = 0
        self._failure_timestamps = []
        self._degraded_mode = False
        self._degraded_mode_until = None
        self._last_successful_update = None

        # Circuit breaker thresholds
        self.MAX_CONSECUTIVE_FAILURES = 3
        self.FAILURE_WINDOW_SECONDS = 300  # 5 minutes
        self.DEGRADED_MODE_DURATION_SECONDS = 900  # 15 minutes

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=min(self.scan_interval, self.force_refresh_interval)
            ),
        )

    def _get_vehicle_identifiers(self) -> str:
        """Get a string identifying the vehicles managed by this coordinator."""
        if not self.vehicle_manager or not self.vehicle_manager.vehicles:
            return "no vehicles"
        vehicle_names = [v.name for v in self.vehicle_manager.vehicles.values()]
        return ", ".join(vehicle_names)

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker should trip to degraded mode.

        Returns True if we should skip API calls and use stale data.
        """
        now = dt_util.now()
        vehicles = self._get_vehicle_identifiers()

        # Check if we're already in degraded mode
        if self._degraded_mode:
            if self._degraded_mode_until and now < self._degraded_mode_until:
                _LOGGER.warning(
                    "Circuit breaker [%s]: In degraded mode until %s. Returning stale data.",
                    vehicles,
                    self._degraded_mode_until
                )
                return True
            else:
                # Cooldown expired, exit degraded mode
                _LOGGER.info("Circuit breaker [%s]: Exiting degraded mode, will retry API", vehicles)
                self._degraded_mode = False
                self._degraded_mode_until = None
                self._consecutive_failures = 0
                self._failure_timestamps.clear()
                return False

        # Clean old failure timestamps outside the window
        cutoff = now - timedelta(seconds=self.FAILURE_WINDOW_SECONDS)
        self._failure_timestamps = [
            ts for ts in self._failure_timestamps if ts > cutoff
        ]

        # Check if we should trip the circuit breaker
        if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            if len(self._failure_timestamps) >= self.MAX_CONSECUTIVE_FAILURES:
                # Trip circuit breaker
                self._degraded_mode = True
                self._degraded_mode_until = now + timedelta(
                    seconds=self.DEGRADED_MODE_DURATION_SECONDS
                )
                _LOGGER.error(
                    "Circuit breaker [%s]: Too many API failures (%d in %d seconds). "
                    "Entering degraded mode until %s. Will return stale data.",
                    vehicles,
                    len(self._failure_timestamps),
                    self.FAILURE_WINDOW_SECONDS,
                    self._degraded_mode_until
                )
                return True

        return False

    def _record_api_failure(self):
        """Record an API failure for circuit breaker tracking."""
        now = dt_util.now()
        self._consecutive_failures += 1
        self._failure_timestamps.append(now)
        vehicles = self._get_vehicle_identifiers()
        _LOGGER.debug(
            "Circuit breaker [%s]: Recorded failure #%d (total in window: %d)",
            vehicles,
            self._consecutive_failures,
            len(self._failure_timestamps)
        )

    def _record_api_success(self):
        """Record an API success, resetting failure counters."""
        vehicles = self._get_vehicle_identifiers()
        if self._consecutive_failures > 0:
            _LOGGER.info(
                "Circuit breaker [%s]: API success after %d failures, resetting counters",
                vehicles,
                self._consecutive_failures
            )
        self._consecutive_failures = 0
        self._failure_timestamps.clear()
        self._last_successful_update = dt_util.now()

        # If we were in degraded mode, exit it early
        if self._degraded_mode:
            _LOGGER.info("Circuit breaker [%s]: API recovered, exiting degraded mode early", vehicles)
            self._degraded_mode = False
            self._degraded_mode_until = None

    @property
    def coordinator_health(self) -> str:
        """Return health status: healthy, unhealthy, or degraded."""
        if self._degraded_mode:
            return "degraded"
        elif self._consecutive_failures > 0:
            return "unhealthy"
        else:
            return "healthy"

    async def _async_update_data(self):
        """Update data via library. Called by update_coordinator periodically.

        Allow to update for the first time without further checking
        Allow force update, if time diff between latest update and `now` is greater than force refresh delta
        """
        # Check circuit breaker before attempting any API calls
        if self._check_circuit_breaker():
            return self.data  # Return stale data without hitting API

        # Check authentication first (auth errors should still propagate)
        try:
            await self.async_check_and_refresh_token()
        except AuthenticationError as AuthError:
            raise ConfigEntryAuthFailed(AuthError) from AuthError

        current_hour = dt_util.now().hour

        # Determine if we should force refresh based on time window
        should_force_refresh = (
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
        )

        if should_force_refresh:
            # Try force refresh
            try:
                await self.hass.async_add_executor_job(
                    self.vehicle_manager.check_and_force_update_vehicles,
                    self.force_refresh_interval,
                )
                self._record_api_success()
                return self.data
            except Exception as ex:
                # Catch EVERYTHING - never let UpdateFailed propagate
                self._record_api_failure()
                _LOGGER.error(
                    "Force refresh failed with %s: %s. Falling back to cached data.",
                    type(ex).__name__,
                    str(ex)
                )
                # Try cached update as fallback
                try:
                    await self.hass.async_add_executor_job(
                        self.vehicle_manager.update_all_vehicles_with_cached_state
                    )
                except Exception as cached_ex:
                    _LOGGER.error("Cached update also failed: %s", str(cached_ex))
                return self.data  # Always return data, never raise UpdateFailed
        else:
            # Cached update path (during no-force-refresh hours)
            try:
                await self.hass.async_add_executor_job(
                    self.vehicle_manager.update_all_vehicles_with_cached_state
                )
                self._record_api_success()
            except Exception as ex:
                self._record_api_failure()
                _LOGGER.error("Cached update failed: %s", str(ex))
            return self.data  # Always return data, never raise UpdateFailed

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

    async def async_check_and_refresh_token(self):
        """Refresh token if needed via library."""
        await self.hass.async_add_executor_job(
            self.vehicle_manager.check_and_refresh_token
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

    async def async_lock_vehicle(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.lock, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_unlock_vehicle(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.unlock, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_open_charge_port(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.open_charge_port, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_close_charge_port(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.close_charge_port, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_climate(
        self, vehicle_id: str, climate_options: ClimateRequestOptions
    ):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.start_climate, vehicle_id, climate_options
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_stop_climate(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.stop_climate, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_charge(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.start_charge, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_stop_charge(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.stop_charge, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_set_charge_limits(self, vehicle_id: str, ac: int, dc: int):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.set_charge_limits, vehicle_id, ac, dc
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_set_charging_current(self, vehicle_id: str, level: int):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.set_charging_current, vehicle_id, level
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_schedule_charging_and_climate(
        self, vehicle_id: str, schedule_options: ScheduleChargingClimateRequestOptions
    ):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.schedule_charging_and_climate,
            vehicle_id,
            schedule_options,
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_hazard_lights(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.start_hazard_lights, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_hazard_lights_and_horn(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.start_hazard_lights_and_horn,
            vehicle_id,
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_start_valet_mode(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.start_valet_mode, vehicle_id
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_stop_valet_mode(self, vehicle_id: str):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.stop_valet_mode,
            vehicle_id,
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_set_v2l_limit(self, vehicle_id: str, limit: int):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.set_vehicle_to_load_discharge_limit, vehicle_id, limit
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )

    async def async_set_windows(
        self, vehicle_id: str, windowOptions: WindowRequestOptions
    ):
        await self.async_check_and_refresh_token()
        action_id = await self.hass.async_add_executor_job(
            self.vehicle_manager.set_windows_state, vehicle_id, windowOptions
        )
        self.hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )
