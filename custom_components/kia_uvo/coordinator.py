"""Coordinator for Hyundai / Kia Connect integration."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import traceback
from collections.abc import Callable
from datetime import timedelta
from functools import partial
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from hyundai_kia_connect_api import (
    ClimateRequestOptions,
    POIInfo,
    ScheduleChargingClimateRequestOptions,
    SVMDetails,
    Token,
    Vehicle,
    VehicleManager,
    WindowRequestOptions,
)
from hyundai_kia_connect_api.const import WINDOW_STATE
from hyundai_kia_connect_api.exceptions import (
    AuthenticationError,
    UnsupportedControlError,
)
from hyundai_kia_connect_api.svm_image import render_views

from .const import (
    CONF_BRAND,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_NO_FORCE_REFRESH_HOUR_FINISH,
    CONF_NO_FORCE_REFRESH_HOUR_START,
    CONF_TOKEN,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
    DEFAULT_ENABLE_GEOLOCATION_ENTITY,
    DEFAULT_FORCE_REFRESH_INTERVAL,
    DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH,
    DEFAULT_NO_FORCE_REFRESH_HOUR_START,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
    DOMAIN,
    OffPeakChargingMode,
)

_LOGGER = logging.getLogger(__name__)

DEPARTURE_DEBOUNCE_SECONDS: Final[float] = 2.5

# Render-invalidation signal for the SVM image entities: sent by
# set_svm_dewarp, consumed in image.py.
SIGNAL_SVM_RENDER = DOMAIN + "_{}_svm_render"


class HyundaiKiaConnectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.platforms: set[str] = set()
        self._action_lock = asyncio.Lock()
        self._svm_details: dict[str, SVMDetails] = {}
        # Per-vehicle SVM fisheye dewarp toggle (local UI state, off by default).
        self._svm_dewarp: dict[str, bool] = {}
        # Rendered SVM views cache: vehicle_id -> ((captured_at, dewarp), views).
        # Invalidated by key change on a new capture or a switch toggle — no
        # explicit invalidation hooks needed.
        self._svm_views: dict[
            str, tuple[tuple[dt.datetime | None, bool], dict[str, bytes]]
        ] = {}

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
        _LOGGER.debug(
            "%s - Polling configured: scan_interval=%ds, "
            "force_refresh_interval=%ds, update_interval=%ds, "
            "no_force_refresh_hours=%d-%d",
            DOMAIN,
            self.scan_interval,
            self.force_refresh_interval,
            min(self.scan_interval, self.force_refresh_interval),
            self.no_force_refresh_hour_start,
            self.no_force_refresh_hour_finish,
        )
        self._pending_departure_options: dict[
            str, ScheduleChargingClimateRequestOptions
        ] = {}
        self._departure_debounce_timers: dict[str, Any] = {}

    @property
    def _pending_departure_options_map(
        self,
    ) -> dict[str, ScheduleChargingClimateRequestOptions]:
        if not hasattr(self, "_pending_departure_options"):
            self._pending_departure_options = {}
        return self._pending_departure_options

    @property
    def _departure_debounce_timers_map(self) -> dict[str, Any]:
        if not hasattr(self, "_departure_debounce_timers"):
            self._departure_debounce_timers = {}
        return self._departure_debounce_timers

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library. Called by update_coordinator periodically.

        Allow to update for the first time without further checking
        Allow force update, if time diff between latest update and `now` is greater than force refresh delta
        """
        _LOGGER.debug(
            "%s - _async_update_data called, scan_interval=%ds, force_refresh_interval=%ds",
            DOMAIN,
            self.scan_interval,
            self.force_refresh_interval,
        )
        try:
            await self.async_check_and_refresh_token()
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
        self.async_set_updated_data(self.data)

    async def async_force_update_all(self) -> None:
        """Force refresh vehicle data and update it."""
        await self.async_check_and_refresh_token()
        await self.hass.async_add_executor_job(
            self.vehicle_manager.force_refresh_all_vehicles_states
        )
        self.async_set_updated_data(self.data)

    async def async_force_refresh_vehicle(self, vehicle_id: str) -> None:
        """Force refresh a single vehicle's state."""
        await self.async_check_and_refresh_token()
        await self.hass.async_add_executor_job(
            self.vehicle_manager.force_refresh_vehicle_state, vehicle_id
        )
        self.async_set_updated_data(self.data)

    async def async_supports_svm(self, vehicle_id: str) -> bool:
        """Return whether the given vehicle supports SVM.

        Capability is a per-region class attribute stamped on the Vehicle by
        the API library (like supports_window_control), so this is a plain
        attribute read — no API call, no executor job needed.
        """
        vehicle = self.vehicle_manager.vehicles.get(vehicle_id)
        if vehicle is None:
            return False
        return bool(vehicle.supports_svm)

    def svm_dewarp_enabled(self, vehicle_id: str) -> bool:
        """Return the per-vehicle SVM fisheye dewarp preference."""
        return self._svm_dewarp.get(vehicle_id, False)

    def set_svm_dewarp(self, vehicle_id: str, enabled: bool) -> None:
        """Set the per-vehicle SVM fisheye dewarp preference."""
        self._svm_dewarp[vehicle_id] = enabled
        # The render key changes with the toggle, but captured_at does not —
        # without this signal the image proxy keeps serving the pre-toggle
        # image until the next capture.
        async_dispatcher_send(self.hass, SIGNAL_SVM_RENDER.format(vehicle_id))

    def get_cached_svm_details(self, vehicle_id: str) -> SVMDetails | None:
        """Return cached SVM details for a vehicle, or None if not yet fetched."""
        return self._svm_details.get(vehicle_id)

    async def async_get_svm_details(self, vehicle_id: str) -> SVMDetails:
        """Fetch the latest cached SVM image and metadata from the API."""
        details = await self.hass.async_add_executor_job(
            self.vehicle_manager.get_svm_details, vehicle_id
        )
        self._svm_details[vehicle_id] = details
        return details

    async def async_request_svm_capture(self, vehicle_id: str) -> SVMDetails:
        """Trigger a fresh SVM capture and update the cached details."""
        details = await self.hass.async_add_executor_job(
            self.vehicle_manager.request_svm_capture,
            vehicle_id,
            True,  # acknowledged_warning — capture is always a user-initiated action
        )
        self._svm_details[vehicle_id] = details
        self.async_set_updated_data(self.data)
        return details

    async def async_get_svm_views(self, vehicle_id: str) -> dict[str, bytes] | None:
        """Return the 5 rendered SVM views (front/rear/left/right/top) as JPEG.

        Renders once per (captured_at, dewarp switch) state: every image
        entity serves from the same dict, and a new capture or a switch
        toggle invalidates it by key change. The render runs in an executor
        thread (dewarp is CPU-bound numpy work); render errors (e.g. missing
        Pillow) propagate to the caller.
        """
        details = self.get_cached_svm_details(vehicle_id)
        if details is None or not details.image_bytes or not details.image_sizes:
            return None
        key = (details.captured_at, self.svm_dewarp_enabled(vehicle_id))
        cached = self._svm_views.get(vehicle_id)
        if cached is not None and cached[0] == key:
            return cached[1]
        views: dict[str, bytes] = await self.hass.async_add_executor_job(
            partial(render_views, details, dewarp=key[1])
        )
        self._svm_views[vehicle_id] = (key, views)
        return views

    async def async_check_and_refresh_token(self) -> None:
        """Refresh token if needed via library."""
        await self.hass.async_add_executor_job(
            self.vehicle_manager.check_and_refresh_token
        )
        await self._async_save_token()

    async def async_await_action_and_refresh(
        self, vehicle_id: str, action_id: str
    ) -> None:
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

    async def async_await_action_and_force_refresh(
        self, vehicle_id: str, action_id: str
    ) -> None:
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
                _LOGGER.exception("Force refresh after call failed")
            self.async_set_updated_data(self.data)

    async def _async_send_action(
        self,
        vehicle_id: str,
        action_fn: Callable[[], Any],
        error_label: str,
        *,
        force_refresh: bool = False,
    ) -> None:
        """Send a vehicle action, wait for completion, and refresh data.

        Serializes actions with a lock to prevent DuplicateRequestError
        from the Hyundai API when commands overlap. If another action is
        already in progress, raises HomeAssistantError immediately so
        the user gets a clear message instead of a mysterious long wait.
        """
        if self._action_lock.locked():
            _LOGGER.warning(
                "Vehicle action '%s' rejected: another action is already in progress",
                error_label,
            )
            raise HomeAssistantError(
                "Another vehicle action is in progress. "
                "Please wait for it to complete and try again."
            )
        async with self._action_lock:
            await self.async_check_and_refresh_token()
            try:
                action_id = await self.hass.async_add_executor_job(action_fn)
            except UnsupportedControlError as err:
                raise HomeAssistantError(
                    f"Vehicle does not support this action: {err}"
                ) from err
            except Exception as err:
                raise HomeAssistantError(f"Failed to {error_label}: {err}") from err
            try:
                if force_refresh:
                    await self.async_await_action_and_force_refresh(
                        vehicle_id, action_id
                    )
                else:
                    await self.async_await_action_and_refresh(vehicle_id, action_id)
            except Exception:
                _LOGGER.exception(
                    "Action '%s' was sent but confirmation polling failed",
                    error_label,
                )

    async def async_lock_vehicle(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.lock(vehicle_id),
            "lock vehicle",
        )

    async def async_unlock_vehicle(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.unlock(vehicle_id),
            "unlock vehicle",
        )

    async def async_open_charge_port(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.open_charge_port(vehicle_id),
            "open charge port",
        )

    async def async_close_charge_port(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.close_charge_port(vehicle_id),
            "close charge port",
        )

    async def async_start_climate_default(self, vehicle_id: str) -> None:
        """Start climate with default options (API fills sensible defaults)."""
        await self.async_start_climate(vehicle_id, ClimateRequestOptions())

    async def async_start_climate(
        self, vehicle_id: str, climate_options: ClimateRequestOptions
    ) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_climate(vehicle_id, climate_options),
            "start climate",
        )

    async def async_stop_climate(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.stop_climate(vehicle_id),
            "stop climate",
        )

    async def async_start_charge(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_charge(vehicle_id),
            "start charge",
        )

    async def async_stop_charge(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.stop_charge(vehicle_id),
            "stop charge",
        )

    async def async_set_charge_limits(self, vehicle_id: str, ac: int, dc: int) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_charge_limits(vehicle_id, ac, dc),
            "set charge limits",
        )

    async def async_set_charging_current(self, vehicle_id: str, level: int) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_charging_current(vehicle_id, level),
            "set charging current",
        )

    async def async_schedule_charging_and_climate(
        self, vehicle_id: str, schedule_options: ScheduleChargingClimateRequestOptions
    ) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.schedule_charging_and_climate(
                vehicle_id, schedule_options
            ),
            "schedule charging and climate",
        )

    def _build_schedule_options_from_vehicle(
        self, vehicle: Vehicle
    ) -> ScheduleChargingClimateRequestOptions:
        """Build schedule options from current vehicle state for partial updates."""
        return ScheduleChargingClimateRequestOptions(
            first_departure=ScheduleChargingClimateRequestOptions.DepartureOptions(
                enabled=vehicle.ev_first_departure_enabled or False,
                days=vehicle.ev_first_departure_days or [0],
                time=vehicle.ev_first_departure_time or dt.time(),
            ),
            second_departure=ScheduleChargingClimateRequestOptions.DepartureOptions(
                enabled=vehicle.ev_second_departure_enabled or False,
                days=vehicle.ev_second_departure_days or [0],
                time=vehicle.ev_second_departure_time or dt.time(),
            ),
            charging_enabled=vehicle.ev_schedule_charge_enabled or False,
            off_peak_start_time=vehicle.ev_off_peak_start_time or dt.time(),
            off_peak_end_time=vehicle.ev_off_peak_end_time or dt.time(),
            off_peak_charge_only_enabled=vehicle.ev_off_peak_charge_only_enabled
            or False,
            climate_enabled=vehicle.ev_first_departure_climate_enabled or False,
            temperature=vehicle.ev_first_departure_climate_temperature or 21.0,
            temperature_unit=vehicle._ev_first_departure_climate_temperature_unit or 0,
            defrost=vehicle.ev_first_departure_climate_defrost or False,
        )

    def _build_departure_options_from_vehicle(
        self, vehicle: Vehicle
    ) -> ScheduleChargingClimateRequestOptions:
        """Build schedule options for departure-only updates, leaving charging scope None."""
        return ScheduleChargingClimateRequestOptions(
            first_departure=ScheduleChargingClimateRequestOptions.DepartureOptions(
                enabled=vehicle.ev_first_departure_enabled or False,
                days=list(vehicle.ev_first_departure_days)
                if vehicle.ev_first_departure_days is not None
                else [],
                time=vehicle.ev_first_departure_time or dt.time(),
                climate_enabled=vehicle.ev_first_departure_climate_enabled or False,
                temperature=vehicle.ev_first_departure_climate_temperature or 21.0,
                defrost=vehicle.ev_first_departure_climate_defrost or False,
            ),
            second_departure=ScheduleChargingClimateRequestOptions.DepartureOptions(
                enabled=vehicle.ev_second_departure_enabled or False,
                days=list(vehicle.ev_second_departure_days)
                if vehicle.ev_second_departure_days is not None
                else [],
                time=vehicle.ev_second_departure_time or dt.time(),
                climate_enabled=vehicle.ev_second_departure_climate_enabled or False,
                temperature=vehicle.ev_second_departure_climate_temperature or 21.0,
                defrost=vehicle.ev_second_departure_climate_defrost or False,
            ),
            charging_enabled=None,
            off_peak_start_time=None,
            off_peak_end_time=None,
            off_peak_charge_only_enabled=None,
        )

    def _build_charge_options_from_vehicle(
        self, vehicle: Vehicle
    ) -> ScheduleChargingClimateRequestOptions:
        """Build schedule options for charge-only updates, leaving departure scope None."""
        return ScheduleChargingClimateRequestOptions(
            first_departure=None,
            second_departure=None,
            charging_enabled=vehicle.ev_schedule_charge_enabled or False,
            off_peak_start_time=vehicle.ev_off_peak_start_time or dt.time(),
            off_peak_end_time=vehicle.ev_off_peak_end_time or dt.time(),
            off_peak_charge_only_enabled=vehicle.ev_off_peak_charge_only_enabled
            or False,
            climate_enabled=None,
            temperature=None,
            temperature_unit=None,
            defrost=None,
        )

    async def async_set_schedule_charge_enabled(
        self, vehicle_id: str, enabled: bool
    ) -> None:
        """Toggle scheduled charging on/off."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_charge_options_from_vehicle(vehicle)
        options.charging_enabled = enabled
        await self.async_schedule_charging_and_climate(vehicle_id, options)

    async def async_set_off_peak_charge_only_enabled(
        self, vehicle_id: str, enabled: bool
    ) -> None:
        """Toggle off-peak charge only on/off."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_charge_options_from_vehicle(vehicle)
        options.off_peak_charge_only_enabled = enabled
        await self.async_schedule_charging_and_climate(vehicle_id, options)

    async def async_set_off_peak_charging(
        self,
        vehicle_id: str,
        *,
        mode: OffPeakChargingMode | None = None,
        start: dt.time | None = None,
        end: dt.time | None = None,
    ) -> None:
        """Set the off-peak charging schedule mode and/or window."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_charge_options_from_vehicle(vehicle)
        if mode is not None:
            if mode is OffPeakChargingMode.OFF:
                options.charging_enabled = False
            elif mode is OffPeakChargingMode.TIME:
                options.charging_enabled = True
                options.off_peak_charge_only_enabled = True
            elif mode is OffPeakChargingMode.TARGET:
                options.charging_enabled = True
                options.off_peak_charge_only_enabled = False
        if start is not None:
            options.off_peak_start_time = start
        if end is not None:
            options.off_peak_end_time = end
        await self.async_schedule_charging_and_climate(vehicle_id, options)

    async def _async_stage_departure_update(
        self,
        vehicle_id: str,
        departure_num: int,
        *,
        debounce: bool = True,
        **updates: Any,
    ) -> None:
        """Stage a departure schedule update, optimistically updating vehicle state and debouncing API calls."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        if vehicle_id not in self._pending_departure_options_map:
            options = self._build_departure_options_from_vehicle(vehicle)
            self._pending_departure_options_map[vehicle_id] = options
        else:
            options = self._pending_departure_options_map[vehicle_id]

        target = (
            options.first_departure if departure_num == 1 else options.second_departure
        )

        if "enabled" in updates and updates["enabled"] is not None:
            target.enabled = updates["enabled"]
            if departure_num == 1:
                vehicle.ev_first_departure_enabled = updates["enabled"]
            else:
                vehicle.ev_second_departure_enabled = updates["enabled"]

        if "days" in updates and updates["days"] is not None:
            target.days = updates["days"]
            if departure_num == 1:
                vehicle.ev_first_departure_days = updates["days"]
            else:
                vehicle.ev_second_departure_days = updates["days"]

        if "time" in updates and updates["time"] is not None:
            target.time = updates["time"]
            if departure_num == 1:
                vehicle.ev_first_departure_time = updates["time"]
            else:
                vehicle.ev_second_departure_time = updates["time"]

        if "climate_enabled" in updates and updates["climate_enabled"] is not None:
            target.climate_enabled = updates["climate_enabled"]
            if departure_num == 1:
                vehicle.ev_first_departure_climate_enabled = updates["climate_enabled"]
            else:
                vehicle.ev_second_departure_climate_enabled = updates["climate_enabled"]

        if "temperature" in updates and updates["temperature"] is not None:
            temp_val = float(updates["temperature"])
            target.temperature = temp_val
            if departure_num == 1:
                vehicle.ev_first_departure_climate_temperature = temp_val
            else:
                vehicle.ev_second_departure_climate_temperature = temp_val

        if "defrost" in updates and updates["defrost"] is not None:
            target.defrost = updates["defrost"]
            if departure_num == 1:
                vehicle.ev_first_departure_climate_defrost = updates["defrost"]
            else:
                vehicle.ev_second_departure_climate_defrost = updates["defrost"]

        if hasattr(self, "async_update_listeners"):
            try:
                self.async_update_listeners()
            except Exception:
                pass

        timer = self._departure_debounce_timers_map.pop(vehicle_id, None)
        if timer:
            timer.cancel()

        if not debounce:
            await self._async_flush_departure_update(vehicle_id)
            return

        def _on_timeout() -> None:
            self._departure_debounce_timers_map.pop(vehicle_id, None)
            if (
                hasattr(self, "hass")
                and self.hass is not None
                and hasattr(self.hass, "async_create_task")
            ):
                self.hass.async_create_task(
                    self._async_flush_departure_update(vehicle_id)
                )
            else:
                asyncio.create_task(self._async_flush_departure_update(vehicle_id))

        loop = (
            self.hass.loop
            if hasattr(self, "hass")
            and self.hass is not None
            and hasattr(self.hass, "loop")
            else asyncio.get_running_loop()
        )
        self._departure_debounce_timers_map[vehicle_id] = loop.call_later(
            DEPARTURE_DEBOUNCE_SECONDS, _on_timeout
        )

    async def _async_flush_departure_update(self, vehicle_id: str) -> None:
        """Transmit batched departure options to the vehicle."""
        timer = self._departure_debounce_timers_map.pop(vehicle_id, None)
        if timer:
            timer.cancel()
        options = self._pending_departure_options_map.pop(vehicle_id, None)
        if options is None:
            return
        _LOGGER.debug(
            "%s - Flushing batched departure schedule for %s: slot1=%s, slot2=%s",
            DOMAIN,
            vehicle_id,
            options.first_departure,
            options.second_departure,
        )
        try:
            await self.async_schedule_charging_and_climate(vehicle_id, options)
        except Exception as err:
            _LOGGER.error(
                "%s - Failed to dispatch batched departure schedule for %s: %s",
                DOMAIN,
                vehicle_id,
                err,
            )
            try:
                if (
                    hasattr(self, "hass")
                    and self.hass is not None
                    and hasattr(self.hass, "async_add_executor_job")
                ):
                    await self.hass.async_add_executor_job(
                        self.vehicle_manager.force_refresh_vehicle_state, vehicle_id
                    )
                else:
                    self.vehicle_manager.force_refresh_vehicle_state(vehicle_id)
            except Exception:
                pass
            if hasattr(self, "async_update_listeners"):
                try:
                    self.async_update_listeners()
                except Exception:
                    pass
            raise

    async def async_flush_departure_update(self, vehicle_id: str) -> None:
        """Immediately flush and transmit any pending batched departure schedule for the vehicle."""
        await self._async_flush_departure_update(vehicle_id)

    async def async_set_departure_enabled(
        self,
        vehicle_id: str,
        departure_num: int,
        enabled: bool,
        *,
        debounce: bool = True,
    ) -> None:
        """Toggle a departure schedule on/off."""
        await self._async_stage_departure_update(
            vehicle_id, departure_num, enabled=enabled, debounce=debounce
        )

    async def async_set_departure_time(
        self,
        vehicle_id: str,
        departure_num: int,
        time: dt.time,
        *,
        debounce: bool = True,
    ) -> None:
        """Set departure time for slot 1 or 2."""
        await self._async_stage_departure_update(
            vehicle_id, departure_num, time=time, debounce=debounce
        )

    async def async_set_departure_temperature(
        self,
        vehicle_id: str,
        departure_num: int,
        temperature: float,
        *,
        debounce: bool = True,
    ) -> None:
        """Set departure climate temperature."""
        await self._async_stage_departure_update(
            vehicle_id, departure_num, temperature=temperature, debounce=debounce
        )

    async def async_set_departure_climate_enabled(
        self,
        vehicle_id: str,
        departure_num: int,
        enabled: bool,
        *,
        debounce: bool = True,
    ) -> None:
        """Toggle departure climate on/off."""
        await self._async_stage_departure_update(
            vehicle_id, departure_num, climate_enabled=enabled, debounce=debounce
        )

    async def async_set_departure_defrost(
        self,
        vehicle_id: str,
        departure_num: int,
        enabled: bool,
        *,
        debounce: bool = True,
    ) -> None:
        """Toggle departure defrost on/off."""
        await self._async_stage_departure_update(
            vehicle_id, departure_num, defrost=enabled, debounce=debounce
        )

    async def async_set_departure_days(
        self,
        vehicle_id: str,
        departure_num: int,
        days: list[int],
        *,
        debounce: bool = True,
    ) -> None:
        """Set departure repeating days for slot 1 or 2."""
        await self._async_stage_departure_update(
            vehicle_id, departure_num, days=days, debounce=debounce
        )

    async def async_toggle_departure_day(
        self,
        vehicle_id: str,
        departure_num: int,
        day: int,
        enabled: bool,
        *,
        debounce: bool = True,
    ) -> None:
        """Toggle a specific repeating day for departure slot 1 or 2."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        current_days = list(
            (
                vehicle.ev_first_departure_days
                if departure_num == 1
                else vehicle.ev_second_departure_days
            )
            or []
        )
        current_days = [d for d in current_days if d != 9]
        if enabled:
            if day not in current_days:
                current_days.append(day)
                current_days.sort()
        else:
            if day in current_days:
                current_days.remove(day)
        if not current_days:
            current_days = [9]
        await self.async_set_departure_days(
            vehicle_id, departure_num, current_days, debounce=debounce
        )

    async def async_set_departure_schedule(
        self,
        vehicle_id: str,
        departure_num: int = 1,
        *,
        enabled: bool | None = None,
        days: list[int] | None = None,
        time: dt.time | None = None,
        climate_enabled: bool | None = None,
        temperature: float | None = None,
        temperature_unit: int | None = None,
        defrost: bool | None = None,
        debounce: bool = False,
    ) -> None:
        """Set full departure schedule and preconditioning climate."""
        await self._async_stage_departure_update(
            vehicle_id,
            departure_num,
            enabled=enabled,
            days=days,
            time=time,
            climate_enabled=climate_enabled,
            temperature=temperature,
            defrost=defrost,
            debounce=debounce,
        )

    async def async_start_hazard_lights(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_hazard_lights(vehicle_id),
            "start hazard lights",
        )

    async def async_start_hazard_lights_and_horn(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_hazard_lights_and_horn(vehicle_id),
            "start hazard lights and horn",
        )

    async def async_start_valet_mode(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_valet_mode(vehicle_id),
            "start valet mode",
        )

    async def async_stop_valet_mode(self, vehicle_id: str) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.stop_valet_mode(vehicle_id),
            "stop valet mode",
        )

    async def async_set_v2l_limit(self, vehicle_id: str, limit: int) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_vehicle_to_load_discharge_limit(
                vehicle_id, limit
            ),
            "set V2L limit",
        )

    async def async_set_windows(
        self, vehicle_id: str, windowOptions: WindowRequestOptions
    ) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_windows_state(vehicle_id, windowOptions),
            "set windows",
        )

    async def async_set_navigation(
        self, vehicle_id: str, poi_list: list[POIInfo]
    ) -> None:
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_navigation(vehicle_id, poi_list),
            "set navigation",
        )

    async def async_open_all_windows(self, vehicle_id: str) -> None:
        options = WindowRequestOptions(
            front_left=WINDOW_STATE.OPEN,
            front_right=WINDOW_STATE.OPEN,
            back_left=WINDOW_STATE.OPEN,
            back_right=WINDOW_STATE.OPEN,
        )
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_windows_state(vehicle_id, options),
            "open all windows",
        )

    async def async_close_all_windows(self, vehicle_id: str) -> None:
        options = WindowRequestOptions(
            front_left=WINDOW_STATE.CLOSED,
            front_right=WINDOW_STATE.CLOSED,
            back_left=WINDOW_STATE.CLOSED,
            back_right=WINDOW_STATE.CLOSED,
        )
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_windows_state(vehicle_id, options),
            "close all windows",
        )

    async def async_vent_all_windows(self, vehicle_id: str) -> None:
        options = WindowRequestOptions(
            front_left=WINDOW_STATE.VENTILATION,
            front_right=WINDOW_STATE.VENTILATION,
            back_left=WINDOW_STATE.VENTILATION,
            back_right=WINDOW_STATE.VENTILATION,
        )
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_windows_state(vehicle_id, options),
            "vent all windows",
        )

    async def _async_save_token(self) -> None:
        """Persist the latest token into the config entry."""
        config_entry = self.config_entry
        assert config_entry is not None
        new_token = self.vehicle_manager.token.to_dict()
        # Only update if token actually changed
        if new_token and new_token != config_entry.data.get(CONF_TOKEN):
            updated_data = {**config_entry.data, CONF_TOKEN: new_token}
            self.hass.config_entries.async_update_entry(config_entry, data=updated_data)
