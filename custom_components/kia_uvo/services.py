import logging
from typing import cast
from datetime import datetime


from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import ServiceCall, callback, HomeAssistant
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from homeassistant.helpers import device_registry
from hyundai_kia_connect_api import (
    ClimateRequestOptions,
    ScheduleChargingClimateRequestOptions,
    WindowRequestOptions,
)

from .const import DOMAIN

SERVICE_UPDATE = "update"
SERVICE_FORCE_UPDATE = "force_update"
SERVICE_LOCK = "lock"
SERVICE_UNLOCK = "unlock"
SERVICE_STOP_CLIMATE = "stop_climate"
SERVICE_START_CLIMATE = "start_climate"
SERVICE_START_CHARGE = "start_charge"
SERVICE_STOP_CHARGE = "stop_charge"
SERVICE_SET_CHARGE_LIMIT = "set_charge_limits"
SERVICE_SET_CHARGING_CURRENT = "set_charging_current"
SERVICE_OPEN_CHARGE_PORT = "open_charge_port"
SERVICE_CLOSE_CHARGE_PORT = "close_charge_port"
SERVICE_SCHEDULE_CHARGING_AND_CLIMATE = "schedule_charging_and_climate"
SERVICE_START_HAZARD_LIGHTS = "start_hazard_lights"
SERVICE_START_HAZARD_LIGHTS_AND_HORN = "start_hazard_lights_and_horn"
SERVICE_START_VALET_MODE = "start_valet_mode"
SERVICE_STOP_VALET_MODE = "stop_valet_mode"
SERVICE_SET_WINDOWS = "set_windows"

SUPPORTED_SERVICES = (
    SERVICE_UPDATE,
    SERVICE_FORCE_UPDATE,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    SERVICE_STOP_CLIMATE,
    SERVICE_START_CLIMATE,
    SERVICE_START_CHARGE,
    SERVICE_STOP_CHARGE,
    SERVICE_SET_CHARGE_LIMIT,
    SERVICE_SET_CHARGING_CURRENT,
    SERVICE_OPEN_CHARGE_PORT,
    SERVICE_CLOSE_CHARGE_PORT,
    SERVICE_SCHEDULE_CHARGING_AND_CLIMATE,
    SERVICE_START_HAZARD_LIGHTS,
    SERVICE_START_HAZARD_LIGHTS_AND_HORN,
    SERVICE_START_VALET_MODE,
    SERVICE_STOP_VALET_MODE,
    SERVICE_SET_WINDOWS,
)

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_services(hass: HomeAssistant) -> bool:
    """Set up services for Hyundai Kia Connect"""

    async def async_handle_force_update(call):
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_force_update_all()

    async def async_handle_update(call):
        _LOGGER.debug(f"Call:{call.data}")
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_update_all()

    async def async_handle_start_climate(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        duration = call.data.get("duration")
        set_temp = call.data.get("temperature")
        climate = call.data.get("climate")
        heating = call.data.get("heating")
        defrost = call.data.get("defrost")
        front_left_seat = call.data.get("flseat")
        front_right_seat = call.data.get("frseat")
        rear_left_seat = call.data.get("rlseat")
        rear_right_seat = call.data.get("rrseat")
        steering_wheel = call.data.get("steering_wheel")

        # Confirm values are correct datatype
        if front_left_seat is not None:
            front_left_seat = int(front_left_seat)
        if front_right_seat is not None:
            front_right_seat = int(front_right_seat)
        if rear_left_seat is not None:
            rear_left_seat = int(rear_left_seat)
        if rear_right_seat is not None:
            rear_right_seat = int(rear_right_seat)
        if steering_wheel is not None:
            steering_wheel = int(steering_wheel)

        climate_request_options = ClimateRequestOptions(
            duration=duration,
            set_temp=set_temp,
            climate=climate,
            heating=heating,
            defrost=defrost,
            front_left_seat=front_left_seat,
            front_right_seat=front_right_seat,
            rear_left_seat=rear_left_seat,
            rear_right_seat=rear_right_seat,
            steering_wheel=steering_wheel,
        )
        await coordinator.async_start_climate(vehicle_id, climate_request_options)

    async def async_handle_stop_climate(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_stop_climate(vehicle_id)

    async def async_handle_lock(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_lock_vehicle(vehicle_id)

    async def async_handle_unlock(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_unlock_vehicle(vehicle_id)

    async def async_handle_open_charge_port(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_open_charge_port(vehicle_id)

    async def async_handle_close_charge_port(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_close_charge_port(vehicle_id)

    async def async_handle_start_charge(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_start_charge(vehicle_id)

    async def async_handle_stop_charge(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_stop_charge(vehicle_id)

    async def async_handle_set_charge_limit(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        ac = call.data.get("ac_limit")
        dc = call.data.get("dc_limit")

        if ac is not None and dc is not None:
            await coordinator.async_set_charge_limits(vehicle_id, int(ac), int(dc))
        else:
            _LOGGER.error(
                f"{DOMAIN} - Enable to set charge limits.  Both AC and DC value required, but not provided."
            )

    async def async_handle_set_windows(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        window_options = WindowRequestOptions(
            front_left=call.data.get("flwindow"),
            front_right=call.data.get("frwindow"),
            back_left=call.data.get("rlwindow"),
            back_right=call.data.get("rrwindow"),
        )

        if (
            window_options.front_left is not None
            and window_options.front_right is not None
            and window_options.back_left is not None
            and window_options.back_right is not None
        ):
            await coordinator.async_set_windows(vehicle_id, window_options)
        else:
            _LOGGER.error(f"{DOMAIN} -  All windows value required, but not provided.")

    async def async_handle_set_charging_current(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        current_level = call.data.get("level")

        if current_level is not None:
            await coordinator.async_set_charging_current(vehicle_id, int(current_level))
        else:
            _LOGGER.error(
                f"{DOMAIN} - Enable to set charging current.  Level required, but not provided."
            )

    async def async_handle_schedule_charging_and_climate(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        first_departure_enabled = call.data.get("first_departure_enabled")
        first_departure_days = call.data.get("first_departure_days")
        first_departure_time = call.data.get("first_departure_time")
        second_departure_enabled = call.data.get("second_departure_enabled")
        second_departure_days = call.data.get("second_departure_days")
        second_departure_time = call.data.get("second_departure_time")
        charging_enabled = call.data.get("charging_enabled")
        off_peak_start_time = call.data.get("off_peak_start_time")
        off_peak_end_time = call.data.get("off_peak_end_time")
        off_peak_charge_only_enabled = call.data.get("off_peak_charge_only_enabled")
        climate_enabled = call.data.get("climate_enabled")
        temperature = call.data.get("temperature")
        temperature_unit = call.data.get("temperature_unit")
        defrost = call.data.get("defrost")

        # Confirm values are correct datatype
        def initialize_departure_option(
            departure_enabled, departure_days, departure_time
        ):
            return ScheduleChargingClimateRequestOptions.DepartureOptions(
                enabled=None if departure_enabled is None else bool(departure_enabled),
                days=None
                if departure_days is None
                else [int(day) for day in departure_days],
                time=None
                if departure_time is None
                else datetime.strptime(departure_time, "%H:%M:%S").time(),
            )

        first_departure = initialize_departure_option(
            first_departure_enabled, first_departure_days, first_departure_time
        )
        second_departure = initialize_departure_option(
            second_departure_enabled, second_departure_days, second_departure_time
        )
        if charging_enabled is not None:
            charging_enabled = bool(charging_enabled)
        if off_peak_start_time is not None:
            off_peak_start_time = datetime.strptime(
                off_peak_start_time, "%H:%M:%S"
            ).time()
        if off_peak_end_time is not None:
            off_peak_end_time = datetime.strptime(off_peak_end_time, "%H:%M:%S").time()
        if off_peak_charge_only_enabled is not None:
            off_peak_charge_only_enabled = bool(off_peak_charge_only_enabled)
        if climate_enabled is not None:
            climate_enabled = bool(climate_enabled)
        if temperature is not None:
            temperature = float(temperature)
        if temperature_unit is not None:
            temperature_unit = int(temperature_unit)
        if defrost is not None:
            defrost = bool(defrost)

        schedule_options = ScheduleChargingClimateRequestOptions(
            first_departure=first_departure,
            second_departure=second_departure,
            charging_enabled=charging_enabled,
            off_peak_start_time=off_peak_start_time,
            off_peak_end_time=off_peak_end_time,
            off_peak_charge_only_enabled=off_peak_charge_only_enabled,
            climate_enabled=climate_enabled,
            temperature=temperature,
            temperature_unit=temperature_unit,
            defrost=defrost,
        )
        await coordinator.async_schedule_charging_and_climate(
            vehicle_id, schedule_options
        )

    async def async_handle_start_hazard_lights(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_start_hazard_lights(vehicle_id)

    async def async_handle_start_hazard_lights_and_horn(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_start_hazard_lights_and_horn(vehicle_id)

    async def async_handle_start_valet_mode(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_start_valet_mode(vehicle_id)

    async def async_handle_stop_valet_mode(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_stop_valet_mode(vehicle_id)

    services = {
        SERVICE_FORCE_UPDATE: async_handle_force_update,
        SERVICE_UPDATE: async_handle_update,
        SERVICE_START_CLIMATE: async_handle_start_climate,
        SERVICE_STOP_CLIMATE: async_handle_stop_climate,
        SERVICE_LOCK: async_handle_lock,
        SERVICE_UNLOCK: async_handle_unlock,
        SERVICE_START_CHARGE: async_handle_start_charge,
        SERVICE_STOP_CHARGE: async_handle_stop_charge,
        SERVICE_SET_CHARGE_LIMIT: async_handle_set_charge_limit,
        SERVICE_OPEN_CHARGE_PORT: async_handle_open_charge_port,
        SERVICE_CLOSE_CHARGE_PORT: async_handle_close_charge_port,
        SERVICE_SET_CHARGING_CURRENT: async_handle_set_charging_current,
        SERVICE_SCHEDULE_CHARGING_AND_CLIMATE: async_handle_schedule_charging_and_climate,
        SERVICE_START_HAZARD_LIGHTS: async_handle_start_hazard_lights,
        SERVICE_START_HAZARD_LIGHTS_AND_HORN: async_handle_start_hazard_lights_and_horn,
        SERVICE_START_VALET_MODE: async_handle_start_valet_mode,
        SERVICE_STOP_VALET_MODE: async_handle_stop_valet_mode,
        SERVICE_SET_WINDOWS: async_handle_set_windows,
    }

    for service in SUPPORTED_SERVICES:
        hass.services.async_register(DOMAIN, service, services[service])
    return True


@callback
def async_unload_services(hass) -> None:
    for service in SUPPORTED_SERVICES:
        hass.services.async_remove(DOMAIN, service)


def _get_vehicle_id_from_device(hass: HomeAssistant, call: ServiceCall) -> str:
    coordinators = list(hass.data[DOMAIN].keys())
    if len(coordinators) == 1:
        coordinator = hass.data[DOMAIN][coordinators[0]]
        vehicles = coordinator.vehicle_manager.vehicles
        if len(vehicles) == 1:
            return list(vehicles.keys())[0]

    device_entry = device_registry.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
    for entry in device_entry.identifiers:
        if entry[0] == DOMAIN:
            vehicle_id = entry[1]
    return vehicle_id


def _get_coordinator_from_device(
    hass: HomeAssistant, call: ServiceCall
) -> HyundaiKiaConnectDataUpdateCoordinator:
    coordinators = list(hass.data[DOMAIN].keys())
    if len(coordinators) == 1:
        return hass.data[DOMAIN][coordinators[0]]
    else:
        device_entry = device_registry.async_get(hass).async_get(
            call.data[ATTR_DEVICE_ID]
        )
        config_entry_ids = device_entry.config_entries
        config_entry_id = next(
            (
                config_entry_id
                for config_entry_id in config_entry_ids
                if cast(
                    ConfigEntry,
                    hass.config_entries.async_get_entry(config_entry_id),
                ).domain
                == DOMAIN
            ),
            None,
        )
        config_entry_unique_id = hass.config_entries.async_get_entry(
            config_entry_id
        ).unique_id
        return hass.data[DOMAIN][config_entry_unique_id]
