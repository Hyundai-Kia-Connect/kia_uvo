import logging

import voluptuous as vol
import asyncio

import homeassistant.helpers.config_validation as cv
from homeassistant import bootstrap
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import *
from .Token import Token
from .Vehicle import Vehicle
from .KiaUvoApi import KiaUvoApi
from datetime import datetime, timezone

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


async def async_setup(hass: HomeAssistant, config):
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    async def async_handle_force_update(call):
        vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
        await vehicle.force_update()

    async def async_handle_update(call):
        vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
        await vehicle.update()

    async def async_handle_start_climate(call):
        vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
        await vehicle.start_climate()

    async def async_handle_stop_climate(call):
        vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
        await vehicle.stop_climate()

    hass.services.async_register(DOMAIN, "force_update", async_handle_force_update)
    hass.services.async_register(DOMAIN, "update", async_handle_update)
    hass.services.async_register(DOMAIN, "start_climate", async_handle_start_climate)
    hass.services.async_register(DOMAIN, "stop_climate", async_handle_stop_climate)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    email = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)
    credentials = config_entry.data.get(CONF_STORED_CREDENTIALS)
    try:
        unit_of_measurement = DISTANCE_UNITS[config_entry.options.get(CONF_UNIT_OF_MEASUREMENT)]
    except:
        unit_of_measurement = DEFAULT_DISTANCE_UNIT

    kia_uvo_api = KiaUvoApi(email, password)
    vehicle = Vehicle(hass, config_entry, Token(credentials), kia_uvo_api, unit_of_measurement)

    data = {
        DATA_VEHICLE_INSTANCE: vehicle,
        DATA_VEHICLE_LISTENER_SCHEDULE: {},
        DATA_FORCED_VEHICLE_LISTENER_SCHEDULE: {},
    }

    async def refresh_config_entry():
        is_token_updated = await vehicle.refresh_token()
        if is_token_updated:
            new_data = config_entry.data.copy()
            new_data[CONF_STORED_CREDENTIALS] = vars(vehicle.token)
            hass.config_entries.async_update_entry(config_entry, data = new_data, options = config_entry.options)

    async def update(event_time):
        await refresh_config_entry()
        await vehicle.refresh_token()
        _LOGGER.debug(f"{DOMAIN} - Decide to make a force call {event_time.hour} {NO_FORCE_SCAN_HOUR_START} {NO_FORCE_SCAN_HOUR_FINISH}")

        await vehicle.update()
        if (event_time.hour < NO_FORCE_SCAN_HOUR_START and event_time.hour >= NO_FORCE_SCAN_HOUR_FINISH):
            if datetime.now(TIME_ZONE_EUROPE) - vehicle.last_updated > FORCE_SCAN_INTERVAL:
                try:
                    await vehicle.force_update()
                except Exception as ex:
                    _LOGGER.error(f"{DOMAIN} - Exception in force update : %s", str(ex))
        else:
            _LOGGER.debug(f"{DOMAIN} - We are in silent hour zone / no automatic force updates {event_time}")

    await update(datetime.now())

    for platform in PLATFORMS:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, platform))

    data[DATA_VEHICLE_LISTENER_SCHEDULE] = async_track_time_interval(hass, update, DEFAULT_SCAN_INTERVAL)
    update_listener = config_entry.add_update_listener(async_update_options)
    data[UPDATE_LISTENER] = update_listener
    hass.data[DOMAIN] = data

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
        update_listener = hass.data[DOMAIN][UPDATE_LISTENER]
        update_listener()
        hass.data[DOMAIN] = None

    return unload_ok
