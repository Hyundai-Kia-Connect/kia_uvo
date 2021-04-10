import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import bootstrap
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import *
from .Token import Token
from .Vehicle import Vehicle
from .KiaUvoApi import KiaUvoApi
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistant, config):
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    async def async_handle_force_update(call):
        vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
        await vehicle.async_force_update()
        await vehicle.async_update()
        
    hass.services.async_register(DOMAIN, "force_update", async_handle_force_update)

    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    email = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)
    credentials = config_entry.data.get(CONF_STORED_CREDENTIALS)
    token = Token(credentials)
    kia_uvo_api = KiaUvoApi(email, password)

    _LOGGER.debug(f"{DOMAIN} - Token had generated {vars(token)}")
    vehicle = Vehicle(hass, config_entry, token, kia_uvo_api)

    data = {
        DATA_VEHICLE_INSTANCE: vehicle,
        DATA_VEHICLE_LISTENER_SCHEDULE: {},
        DATA_FORCED_VEHICLE_LISTENER_SCHEDULE: {}
    }

    async def refresh_token():
        is_token_updated = vehicle.refresh_token()
        if is_token_updated:
            new_data = config_entry.data.copy()
            new_data[CONF_STORED_CREDENTIALS] = vars(vehicle._token)
            hass.config_entries.async_update_entry(config_entry, data=new_data, options=config_entry.options)

    async def update(event_time):
        await refresh_token()
        _LOGGER.debug(f"{DOMAIN}Decide to make a force call {event_time.hour} {NO_FORCE_SCAN_HOUR_START} {NO_FORCE_SCAN_HOUR_FINISH}")

        await vehicle.async_update()
        if (event_time.hour < NO_FORCE_SCAN_HOUR_START and event_time.hour >= NO_FORCE_SCAN_HOUR_FINISH):

            _LOGGER.debug(f"{DOMAIN}We are in force hour zone {event_time}")
            _LOGGER.debug(f"{DOMAIN}Check last update of vehicle {vehicle.last_updated} {datetime.now()} {FORCE_SCAN_INTERVAL}")

            if (datetime.now() - vehicle.last_updated > FORCE_SCAN_INTERVAL):
                try:
                    await vehicle.async_force_update()
                    await vehicle.async_update()
                except Exception as ex:
                    _LOGGER.error(f"{DOMAIN} Exception in force update : %s", str(ex))


    await update(datetime.now())

    for component in PLATFORMS:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, component))

    data[DATA_VEHICLE_LISTENER_SCHEDULE] = async_track_time_interval(
        hass, update, DEFAULT_SCAN_INTERVAL
    )

    hass.data[DOMAIN] = data

    return True
