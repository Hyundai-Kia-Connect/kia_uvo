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

    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    email = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)
    credentials = config_entry.data.get(CONF_STORED_CREDENTIALS)
    token = Token(
        access_token = credentials.get('access_token'),
        refresh_token = credentials.get('refresh_token'),
        device_id = credentials.get('device_id'),
        vehicle_name = credentials.get('vehicle_name'),
        vehicle_id = credentials.get('vehicle_id'),
        vehicle_model = credentials.get('vehicle_model'),
        vehicle_registration_date = credentials.get('vehicle_registration_date')
    )

    _LOGGER.debug(f"Token had generated {vars(token)}")

    data = {
        DATA_VEHICLE_INSTANCE: Vehicle(hass, config_entry, token),
        DATA_VEHICLE_LISTENER_SCHEDULE: {},
        DATA_FORCED_VEHICLE_LISTENER_SCHEDULE: {}
    }

    await data[DATA_VEHICLE_INSTANCE].async_update()

    for component in PLATFORMS:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, component))

    async def update(event_time):
        await data[DATA_VEHICLE_INSTANCE].async_update()

    async def force_update(event_time):
        if not (event_time.hour >= NO_FORCE_SCAN_HOUR_START or event_time.hour >= NO_FORCE_SCAN_HOUR_FINISH):
            await data[DATA_VEHICLE_INSTANCE].async_force_update()
            
        await data[DATA_VEHICLE_INSTANCE].async_update()

    data[DATA_VEHICLE_LISTENER_SCHEDULE] = async_track_time_interval(
        hass, update, DEFAULT_SCAN_INTERVAL
    )

    data[DATA_FORCED_VEHICLE_LISTENER_SCHEDULE] = async_track_time_interval(
        hass, force_update, FORCE_SCAN_INTERVAL
    )

    hass.data[DOMAIN] = data

    return True
