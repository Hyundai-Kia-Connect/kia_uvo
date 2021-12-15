import logging

import asyncio
import voluptuous as vol
from datetime import datetime, timezone, timedelta

from homeassistant import bootstrap
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_REGION,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .utils import DEFAULT_DISTANCE_UNIT_ARRAY, get_default_distance_unit

from .const import (
    DOMAIN,
    DATA_VEHICLE_INSTANCE,
    DATA_CONFIG_UPDATE_LISTENER,
    DATA_VEHICLE_LISTENER,
    DEFAULT_BRAND,
    DEFAULT_PIN,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
    CONF_BRAND,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_FORCE_SCAN_INTERVAL,
    CONF_PIN,
    CONF_NO_FORCE_SCAN_HOUR_FINISH,
    CONF_NO_FORCE_SCAN_HOUR_START,
    CONF_SCAN_INTERVAL,
    CONF_STORED_CREDENTIALS,
    CONF_VEHICLE_IDENTIFIER,
    DISTANCE_UNITS,
    DEFAULT_NO_FORCE_SCAN_HOUR_FINISH,
    DEFAULT_NO_FORCE_SCAN_HOUR_START,
    DEFAULT_FORCE_SCAN_INTERVAL,
    DEFAULT_ENABLE_GEOLOCATION_ENTITY,
    DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
    PLATFORMS,
)
from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token
from .utils import get_implementation_by_region_brand
from .Vehicle import Vehicle

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config_entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    def convert_call_to_vehicle(call) -> Vehicle:
        vehicle_identifiers = list(hass.data[DOMAIN].keys())
        if len(vehicle_identifiers) == 1:
            vehicle_identifier = vehicle_identifiers[0]
        else:
            vehicle_identifier = convert_device_id_to_vehicle_identifier(
                call.data[ATTR_DEVICE_ID]
            )

        return hass.data[DOMAIN][vehicle_identifier][DATA_VEHICLE_INSTANCE]

    def convert_device_id_to_vehicle_identifier(device_id: str) -> str:
        device_registry = dr.async_get(hass)
        device_entry: dr.DeviceEntry = device_registry.async_get(device_id)
        return list(device_entry.identifiers.copy().pop())[1]

    async def async_handle_force_update(call):
        vehicle: Vehicle = convert_call_to_vehicle(call)
        await vehicle.force_update()

    async def async_handle_update(call):
        vehicle: Vehicle = convert_call_to_vehicle(call)
        await vehicle.update()

    async def async_handle_start_climate(call):
        set_temp = call.data.get("Temperature")
        duration = call.data.get("Duration")
        defrost = call.data.get("Defrost")
        climate = call.data.get("Climate")
        heating = call.data.get("Heating")
        vehicle: Vehicle = convert_call_to_vehicle(call)
        await vehicle.start_climate(set_temp, duration, defrost, climate, heating)

    async def async_handle_stop_climate(call):
        vehicle: Vehicle = convert_call_to_vehicle(call)
        await vehicle.stop_climate()

    async def async_handle_start_charge(call):
        vehicle: Vehicle = convert_call_to_vehicle(call)
        await vehicle.start_charge()

    async def async_handle_stop_charge(call):
        vehicle: Vehicle = convert_call_to_vehicle(call)
        await vehicle.stop_charge()

    async def async_handle_set_charge_limits(call):
        ac_limit = call.data.get("ac_limit")
        dc_limit = call.data.get("dc_limit")
        vehicle: Vehicle = convert_call_to_vehicle(call)
        await vehicle.set_charge_limits(ac_limit, dc_limit)

    hass.services.async_register(DOMAIN, "force_update", async_handle_force_update)
    hass.services.async_register(DOMAIN, "update", async_handle_update)
    hass.services.async_register(DOMAIN, "start_climate", async_handle_start_climate)
    hass.services.async_register(DOMAIN, "stop_climate", async_handle_stop_climate)
    hass.services.async_register(DOMAIN, "start_charge", async_handle_start_charge)
    hass.services.async_register(DOMAIN, "stop_charge", async_handle_stop_charge)
    hass.services.async_register(
        DOMAIN, "set_charge_limits", async_handle_set_charge_limits
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    _LOGGER.debug(f"{DOMAIN} - async_setup_entry started - {config_entry}")
    vehicle_identifier = config_entry.data[CONF_VEHICLE_IDENTIFIER]
    username = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)
    pin = config_entry.data.get(CONF_PIN, DEFAULT_PIN)
    region = config_entry.data.get(CONF_REGION, DEFAULT_REGION)
    brand = config_entry.data.get(CONF_BRAND, DEFAULT_BRAND)
    credentials = config_entry.data.get(CONF_STORED_CREDENTIALS)

    if len(DEFAULT_DISTANCE_UNIT_ARRAY) == 0:
        system_default_distance_unit = hass.config.as_dict()["unit_system"]["length"]
        DEFAULT_DISTANCE_UNIT_ARRAY.append(
            list(DISTANCE_UNITS.keys())[
                list(DISTANCE_UNITS.values()).index(system_default_distance_unit)
            ]
        )

    unit_of_measurement = DISTANCE_UNITS[
        config_entry.options.get(CONF_UNIT_OF_MEASUREMENT, get_default_distance_unit())
    ]
    no_force_scan_hour_start = config_entry.options.get(
        CONF_NO_FORCE_SCAN_HOUR_START, DEFAULT_NO_FORCE_SCAN_HOUR_START
    )
    no_force_scan_hour_finish = config_entry.options.get(
        CONF_NO_FORCE_SCAN_HOUR_FINISH, DEFAULT_NO_FORCE_SCAN_HOUR_FINISH
    )
    scan_interval = timedelta(
        minutes=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    force_scan_interval = timedelta(
        minutes=config_entry.options.get(
            CONF_FORCE_SCAN_INTERVAL, DEFAULT_FORCE_SCAN_INTERVAL
        )
    )
    enable_geolocation_entity = config_entry.options.get(
        CONF_ENABLE_GEOLOCATION_ENTITY, DEFAULT_ENABLE_GEOLOCATION_ENTITY
    )
    use_email_with_geocode_api = config_entry.options.get(
        CONF_USE_EMAIL_WITH_GEOCODE_API, DEFAULT_USE_EMAIL_WITH_GEOCODE_API
    )

    kia_uvo_api: KiaUvoApiImpl = get_implementation_by_region_brand(
        region, brand, username, password, use_email_with_geocode_api, pin
    )
    vehicle: Vehicle = Vehicle(
        hass,
        config_entry,
        Token(credentials),
        kia_uvo_api,
        unit_of_measurement,
        enable_geolocation_entity,
        region,
    )

    data = {
        DATA_VEHICLE_INSTANCE: vehicle,
        DATA_VEHICLE_LISTENER: None,
        DATA_CONFIG_UPDATE_LISTENER: None,
    }

    async def refresh_config_entry():
        is_token_updated = await vehicle.refresh_token()
        if is_token_updated:
            new_data = config_entry.data.copy()
            new_data[CONF_STORED_CREDENTIALS] = vars(vehicle.token)
            hass.config_entries.async_update_entry(
                config_entry, data=new_data, options=config_entry.options
            )

    async def update(event_time_utc: datetime):
        await refresh_config_entry()
        #await vehicle.refresh_token()
        local_timezone = vehicle.kia_uvo_api.get_timezone_by_region()
        event_time_local = dt_util.as_local(event_time_utc)

        await vehicle.update()
        call_force_update = False

        if (
            event_time_local.hour < no_force_scan_hour_start
            and event_time_local.hour >= no_force_scan_hour_finish
        ):
            if (
                datetime.now(local_timezone) - vehicle.last_updated
                > force_scan_interval
            ):
                call_force_update = True

        if call_force_update == True:
            try:
                await vehicle.force_update()
            except Exception as ex:
                _LOGGER.error(f"{DOMAIN} - Exception in force update : %s", str(ex))

    await update(dt_util.utcnow())

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    data[DATA_VEHICLE_LISTENER] = async_track_time_interval(hass, update, scan_interval)
    data[DATA_CONFIG_UPDATE_LISTENER] = config_entry.add_update_listener(
        async_update_options
    )
    hass.data[DOMAIN][vehicle_identifier] = data

    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry):
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        vehicle_identifier = config_entry.data[CONF_VEHICLE_IDENTIFIER]
        vehicle_listener = hass.data[DOMAIN][vehicle_identifier][DATA_VEHICLE_LISTENER]
        vehicle_listener()

        config_update_listener = hass.data[DOMAIN][vehicle_identifier][
            DATA_CONFIG_UPDATE_LISTENER
        ]
        config_update_listener()

        hass.data[DOMAIN][vehicle_identifier] = None

    return unload_ok

async def async_migrate_entry(hass, config_entry: ConfigEntry):

    if config_entry.version == 1:
        new = config_entry.data
        _LOGGER.debug(f"{DOMAIN} - New: {new}")

        #hass.data[DOMAIN] = []
        #hass.data[DOMAIN][stored_credentials.vehicle_id] = vehicle_data_temp
        #new = {}
        #hass.config_entries.async_update_entry(config_entry, data=new)
        #config_entry.version = 2
    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
