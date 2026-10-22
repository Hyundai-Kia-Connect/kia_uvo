"""Coordinator for Hyundai / Kia Connect integration."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections.abc import Callable
from datetime import timedelta
from functools import partial
from typing import Any, Literal

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
    APIError,
    AuthenticationError,
    RateLimitingError,
    UnsupportedControlError,
)
from hyundai_kia_connect_api.svm_image import render_views

from .const import (
    CONF_BRAND,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_EXCLUDED_VEHICLES,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_NO_FORCE_REFRESH_HOUR_FINISH,
    CONF_NO_FORCE_REFRESH_HOUR_START,
    CONF_TOKEN,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
    DEFAULT_ENABLE_GEOLOCATION_ENTITY,
    DEFAULT_EXCLUDED_VEHICLES,
    DEFAULT_FORCE_REFRESH_INTERVAL,
    DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH,
    DEFAULT_NO_FORCE_REFRESH_HOUR_START,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
    DOMAIN,
    OffPeakChargingMode,
)

_LOGGER = logging.getLogger(__name__)

# Render-invalidation signal for the SVM image entities: sent by
# set_svm_dewarp, consumed in image.py.
SIGNAL_SVM_RENDER = DOMAIN + "_{}_svm_render"

# How a single vehicle is polled:
#   check  - let the library decide (force refresh or cached, based on the
#            force refresh interval) - used in the periodic update
#   cached - server-side cached state only
#   force  - explicit fresh read, used by the force update service
PollMode = Literal["check", "cached", "force"]


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
        # Per-vehicle API failure state: vehicle_id -> "ExcType: message".
        # A vehicle in this map has its entities marked unavailable while the
        # rest of the account keeps updating.
        self._vehicle_errors: dict[str, str] = {}
        # Consecutive failed polls per vehicle (drives the "exclude it" hint).
        self._vehicle_failures: dict[str, int] = {}
        # Vehicles the user excluded from polling (VIN or internal id).
        self._excluded_vehicles: set[str] = set(
            config_entry.options.get(CONF_EXCLUDED_VEHICLES, DEFAULT_EXCLUDED_VEHICLES)
        )

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

        in_force_window = (
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

        # Every vehicle is polled on its own: a vehicle the backend no longer
        # serves must not take the rest of the account down with it.
        await self._async_poll_vehicles(mode="check" if in_force_window else "cached")

        return self.data

    async def async_update_all(self) -> None:
        """Update vehicle data."""
        await self.async_check_and_refresh_token()
        await self._async_poll_vehicles(mode="cached")
        self.async_set_updated_data(self.data)

    async def async_force_update_all(self) -> None:
        """Force refresh vehicle data and update it."""
        await self.async_check_and_refresh_token()
        await self._async_poll_vehicles(mode="force")
        self.async_set_updated_data(self.data)

    async def _async_poll_vehicles(self, *, mode: PollMode) -> None:
        """Poll every vehicle on its own, isolating per-vehicle API failures.

        A vehicle that fails does not take the rest of the account down: the
        failure is recorded for that vehicle only, and its entities go
        unavailable. Account-level failures (rate limiting, network, unknown
        exceptions) still abort the whole cycle so Home Assistant can back
        off.
        """
        vehicles = list(self.vehicle_manager.vehicles.items())
        polled = [vid for vid, _ in vehicles if not self._is_vehicle_excluded(vid)]
        auth_failures = 0
        self._apply_vehicle_exclusions()

        for vehicle_id, _vehicle in vehicles:
            if self._is_vehicle_excluded(vehicle_id):
                continue
            try:
                await self._async_poll_vehicle(vehicle_id, mode=mode)
            except AuthenticationError as err:
                # resCode 7501 is a per-vehicle answer, not a dead account.
                auth_failures += 1
                self._record_vehicle_error(vehicle_id, err)
                if auth_failures == len(polled):
                    raise ConfigEntryAuthFailed(err) from err
            except RateLimitingError as err:
                raise UpdateFailed(f"Rate limited by the API: {err}") from err
            except APIError as err:
                self._record_vehicle_error(vehicle_id, err)
            except Exception as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err
            else:
                self._clear_vehicle_error(vehicle_id)

        self._prune_vehicle_state()

    async def _async_poll_vehicle(self, vehicle_id: str, *, mode: PollMode) -> None:
        """Update a single vehicle, falling back to the cached state on force."""
        try:
            if mode == "check":
                await self.hass.async_add_executor_job(
                    self.vehicle_manager.check_and_force_update_vehicle,
                    self.force_refresh_interval,
                    vehicle_id,
                )
            elif mode == "force":
                await self.hass.async_add_executor_job(
                    self.vehicle_manager.force_refresh_vehicle_state,
                    vehicle_id,
                )
            else:
                await self.hass.async_add_executor_job(
                    self.vehicle_manager.update_vehicle_with_cached_state,
                    vehicle_id,
                )
        except APIError:
            if mode == "cached":
                raise
            # A failed force refresh is not fatal: retry this vehicle with the
            # server-side cached state, exactly like the old account-wide
            # fallback did, but scoped to the vehicle that failed.
            await self.hass.async_add_executor_job(
                self.vehicle_manager.update_vehicle_with_cached_state,
                vehicle_id,
            )

    def vehicle_available(self, vehicle_id: str) -> bool:
        """Whether the given vehicle currently has usable data.

        False when the vehicle's last poll failed (its entities go
        unavailable) or when the user excluded it from polling.
        """
        return vehicle_id not in self._vehicle_errors and not self._is_vehicle_excluded(
            vehicle_id
        )

    def vehicle_error(self, vehicle_id: str) -> str | None:
        """The last error recorded for the given vehicle, if any."""
        return self._vehicle_errors.get(vehicle_id)

    def vehicle_errors(self) -> dict[str, str]:
        """All recorded per-vehicle errors, keyed by vehicle id."""
        return dict(self._vehicle_errors)

    def _vehicle_key(self, vehicle: Vehicle) -> str:
        """The stable key of a vehicle: VIN when known, else internal id."""
        vin: str | None = vehicle.VIN
        vehicle_id: str = vehicle.id
        return vin or vehicle_id

    def _is_vehicle_excluded(self, vehicle_id: str) -> bool:
        """Whether the user excluded this vehicle from polling."""
        vehicle = self.vehicle_manager.vehicles.get(vehicle_id)
        if vehicle is None:
            return False
        return self._vehicle_key(vehicle) in self._excluded_vehicles

    def vehicle_excluded(self, vehicle_id: str) -> bool:
        """Whether the given vehicle is excluded from polling."""
        return self._is_vehicle_excluded(vehicle_id)

    def excluded_vehicle_ids(self) -> list[str]:
        """Internal ids of the vehicles excluded from polling."""
        return [
            vehicle_id
            for vehicle_id in self.vehicle_manager.vehicles
            if self._is_vehicle_excluded(vehicle_id)
        ]

    def _apply_vehicle_exclusions(self) -> None:
        """Mirror the exclusion list onto the library's per-vehicle flag.

        Applied on every cycle: the library can add vehicles to the account
        (Kia USA refreshes the vehicle list on token refresh), and a freshly
        added vehicle starts out enabled.
        """
        for vehicle_id in self.vehicle_manager.vehicles:
            if self._is_vehicle_excluded(vehicle_id):
                self.vehicle_manager.disable_vehicle(vehicle_id)
            else:
                self.vehicle_manager.enable_vehicle(vehicle_id)

    def _record_vehicle_error(self, vehicle_id: str, err: Exception) -> None:
        """Remember a per-vehicle failure and mark the vehicle unavailable."""
        vehicle = self.vehicle_manager.vehicles.get(vehicle_id)
        label = (vehicle.name if vehicle else None) or vehicle_id
        self._vehicle_errors[vehicle_id] = f"{type(err).__name__}: {err}"
        failures = self._vehicle_failures.get(vehicle_id, 0) + 1
        self._vehicle_failures[vehicle_id] = failures
        _LOGGER.warning(
            "%s - Failed to update vehicle %s (%s): %s",
            DOMAIN,
            label,
            vehicle_id,
            err,
        )
        if failures == 3:
            _LOGGER.warning(
                "%s - Vehicle %s (%s) failed %s polls in a row. If the backend no "
                "longer serves it (e.g. the car was sold), exclude it from "
                "polling in the integration options (excluded_vehicles) to stop "
                "these errors.",
                DOMAIN,
                label,
                vehicle_id,
                failures,
            )

    def _clear_vehicle_error(self, vehicle_id: str) -> None:
        """Drop the failure state of a vehicle that answered successfully."""
        self._vehicle_errors.pop(vehicle_id, None)
        self._vehicle_failures.pop(vehicle_id, None)

    def _prune_vehicle_state(self) -> None:
        """Forget state of vehicles that are no longer on the account."""
        known = set(self.vehicle_manager.vehicles)
        for vehicle_id in set(self._vehicle_errors) - known:
            self._vehicle_errors.pop(vehicle_id, None)
        for vehicle_id in set(self._vehicle_failures) - known:
            self._vehicle_failures.pop(vehicle_id, None)

    async def async_force_refresh_vehicle(self, vehicle_id: str) -> None:
        """Force refresh a single vehicle's state."""
        self._assert_vehicle_not_excluded(vehicle_id)
        await self.async_check_and_refresh_token()
        await self.hass.async_add_executor_job(
            self.vehicle_manager.force_refresh_vehicle_state, vehicle_id
        )
        self.async_set_updated_data(self.data)

    def _assert_vehicle_not_excluded(self, vehicle_id: str) -> None:
        """Refuse commands for a vehicle the user excluded from polling."""
        if self._is_vehicle_excluded(vehicle_id):
            raise HomeAssistantError(
                f"Vehicle {vehicle_id} is excluded from polling in the "
                "integration options (excluded_vehicles)."
            )

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
        """Wait for a vehicle action to complete, then refresh the cached data."""
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
        self._assert_vehicle_not_excluded(vehicle_id)
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
        """Lock the vehicle."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.lock(vehicle_id),
            "lock vehicle",
        )

    async def async_unlock_vehicle(self, vehicle_id: str) -> None:
        """Unlock the vehicle."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.unlock(vehicle_id),
            "unlock vehicle",
        )

    async def async_open_charge_port(self, vehicle_id: str) -> None:
        """Open the vehicle's charge port."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.open_charge_port(vehicle_id),
            "open charge port",
        )

    async def async_close_charge_port(self, vehicle_id: str) -> None:
        """Close the vehicle's charge port."""
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
        """Start climate control with the given options."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_climate(vehicle_id, climate_options),
            "start climate",
        )

    async def async_stop_climate(self, vehicle_id: str) -> None:
        """Stop climate control."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.stop_climate(vehicle_id),
            "stop climate",
        )

    async def async_start_charge(self, vehicle_id: str) -> None:
        """Start charging."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_charge(vehicle_id),
            "start charge",
        )

    async def async_stop_charge(self, vehicle_id: str) -> None:
        """Stop charging."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.stop_charge(vehicle_id),
            "stop charge",
        )

    async def async_set_charge_limits(self, vehicle_id: str, ac: int, dc: int) -> None:
        """Set the AC and DC charge limits (percent)."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_charge_limits(vehicle_id, ac, dc),
            "set charge limits",
        )

    async def async_set_charging_current(self, vehicle_id: str, level: int) -> None:
        """Set the AC charging current level."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_charging_current(vehicle_id, level),
            "set charging current",
        )

    async def async_schedule_charging_and_climate(
        self, vehicle_id: str, schedule_options: ScheduleChargingClimateRequestOptions
    ) -> None:
        """Set the charging and climate schedule."""
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

    async def async_set_schedule_charge_enabled(
        self, vehicle_id: str, enabled: bool
    ) -> None:
        """Toggle scheduled charging on/off."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_schedule_options_from_vehicle(vehicle)
        options.charging_enabled = enabled
        await self.async_schedule_charging_and_climate(vehicle_id, options)

    async def async_set_off_peak_charge_only_enabled(
        self, vehicle_id: str, enabled: bool
    ) -> None:
        """Toggle off-peak charge only on/off."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_schedule_options_from_vehicle(vehicle)
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
        """Set the off-peak charging schedule mode and/or window.

        ``mode`` maps to the (charging_enabled, off_peak_charge_only_enabled)
        pair the API expects: ``OFF`` disables scheduled charging, ``TIME``
        charges only during the off-peak window (time priority), ``TARGET``
        prefers off-peak tariffs but continues past the window to reach the
        target SoC (target priority). ``mode=None`` preserves the current mode
        and only adjusts the window — used by the time entities. Other
        schedule fields (departures) are preserved.
        """
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_schedule_options_from_vehicle(vehicle)
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

    async def async_set_departure_enabled(
        self, vehicle_id: str, departure_num: int, enabled: bool
    ) -> None:
        """Toggle a departure schedule on/off."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_schedule_options_from_vehicle(vehicle)
        if departure_num == 1:
            options.first_departure.enabled = enabled
        else:
            options.second_departure.enabled = enabled
        # reservFlag (charging_enabled) must be 1 for departure slots to take
        # effect. If the vehicle doesn't expose ev_schedule_charge_enabled
        # (None), the builder defaults it to False, causing the API to accept
        # the request but ignore per-slot reservChargeSet.
        if enabled and not options.charging_enabled:
            options.charging_enabled = True
        await self.async_schedule_charging_and_climate(vehicle_id, options)

    async def async_set_departure_climate_enabled(
        self, vehicle_id: str, departure_num: int, enabled: bool
    ) -> None:
        """Toggle departure climate on/off."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_schedule_options_from_vehicle(vehicle)
        options.climate_enabled = enabled
        await self.async_schedule_charging_and_climate(vehicle_id, options)

    async def async_set_departure_defrost(
        self, vehicle_id: str, departure_num: int, enabled: bool
    ) -> None:
        """Toggle departure defrost on/off."""
        vehicle = self.vehicle_manager.vehicles[vehicle_id]
        options = self._build_schedule_options_from_vehicle(vehicle)
        options.defrost = enabled
        await self.async_schedule_charging_and_climate(vehicle_id, options)

    async def async_start_hazard_lights(self, vehicle_id: str) -> None:
        """Flash the hazard lights."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_hazard_lights(vehicle_id),
            "start hazard lights",
        )

    async def async_start_hazard_lights_and_horn(self, vehicle_id: str) -> None:
        """Flash the hazard lights and sound the horn."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_hazard_lights_and_horn(vehicle_id),
            "start hazard lights and horn",
        )

    async def async_start_valet_mode(self, vehicle_id: str) -> None:
        """Turn on valet mode."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.start_valet_mode(vehicle_id),
            "start valet mode",
        )

    async def async_stop_valet_mode(self, vehicle_id: str) -> None:
        """Turn off valet mode."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.stop_valet_mode(vehicle_id),
            "stop valet mode",
        )

    async def async_set_v2l_limit(self, vehicle_id: str, limit: int) -> None:
        """Set the vehicle-to-load discharge limit (percent)."""
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
        """Set the state of one or more windows."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_windows_state(vehicle_id, windowOptions),
            "set windows",
        )

    async def async_set_navigation(
        self, vehicle_id: str, poi_list: list[POIInfo]
    ) -> None:
        """Send points of interest to the vehicle's navigation."""
        await self._async_send_action(
            vehicle_id,
            lambda: self.vehicle_manager.set_navigation(vehicle_id, poi_list),
            "set navigation",
        )

    async def async_open_all_windows(self, vehicle_id: str) -> None:
        """Open all four windows."""
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
        """Close all four windows."""
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
        """Put all four windows in the ventilation position."""
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
