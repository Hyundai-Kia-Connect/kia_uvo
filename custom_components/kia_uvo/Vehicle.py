import logging

from datetime import datetime
import re
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_call_later
import homeassistant.util.dt as dt_util

from .const import *
from .Token import Token
from .KiaUvoApi import KiaUvoApi

_LOGGER = logging.getLogger(__name__)

class Vehicle(object):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, token: Token, kia_uvo_api: KiaUvoApi, unit_of_measurement: str, enable_geolocation_entity):
        self.hass = hass
        self.config_entry = config_entry
        self.token = token
        self.kia_uvo_api = kia_uvo_api
        self.unit_of_measurement = unit_of_measurement
        self.enable_geolocation_entity = enable_geolocation_entity

        self.name = token.vehicle_name
        self.model = token.vehicle_model
        self.id = token.vehicle_id
        self.registration_date = token.vehicle_registration_date
        self.vehicle_data = {}
        self.engine_type = None
        self.last_updated: datetime = datetime.min

        self.force_update_try_caller = None

        self.topic_update = TOPIC_UPDATE.format(self.id)
        _LOGGER.debug(f"{DOMAIN} - Received token into Vehicle Object {vars(token)}")

    async def update(self):
        try:
            current_lat = self.get_child_value("vehicleLocation.coord.lat")
            current_lon = self.get_child_value("vehicleLocation.coord.lon")
            current_geocode = self.get_child_value("vehicleLocation.geocodedLocation")
            
            self.vehicle_data = await self.hass.async_add_executor_job(self.kia_uvo_api.get_cached_vehicle_status, self.token)
            self.set_last_updated()
            self.set_engine_type()

            new_lat = self.get_child_value("vehicleLocation.coord.lat")
            new_lon = self.get_child_value("vehicleLocation.coord.lon")

            if self.enable_geolocation_entity == True:
                if (current_lat != new_lat or current_lon != new_lon) or current_geocode is None:
                    self.vehicle_data["vehicleLocation"]["geocodedLocation"] = await self.hass.async_add_executor_job(self.kia_uvo_api.get_geocoded_location, new_lat, new_lon)
                else:
                    self.vehicle_data["vehicleLocation"]["geocodedLocation"] = current_geocode

            async_dispatcher_send(self.hass, self.topic_update)
        except Exception as ex:
            _LOGGER.error(f"{DOMAIN} - Exception in update : %s", str(ex))

    async def force_update(self):
        await self.hass.async_add_executor_job(self.kia_uvo_api.update_vehicle_status, self.token)
        await self.update()

    async def force_update_loop(self, _):
        _LOGGER.debug(f"{DOMAIN} - force_update_loop start {self.force_update_try_count} {COUNT_FORCE_UPDATE_AFTER_COMMAND}")
        if self.force_update_try_count == COUNT_FORCE_UPDATE_AFTER_COMMAND:
            self.force_update_try_count = 0
            return

        last_updated: datetime = self.last_updated
        _LOGGER.debug(f"{DOMAIN} - force_update_loop last_updated {last_updated}")

        await self.force_update()
        _LOGGER.debug(f"{DOMAIN} - force_update_loop force_update_finished {last_updated} {self.last_updated}")
        if last_updated == self.last_updated:
            self.force_update_try_count = self.force_update_try_count + 1
            self.force_update_try_caller = async_call_later(self.hass, INTERVAL_FORCE_UPDATE_AFTER_COMMAND, self.force_update_loop)        

    async def lock_action(self, action: VEHICLE_LOCK_ACTION):
        await self.hass.async_add_executor_job(self.kia_uvo_api.lock_action, self.token, action.value)
        self.force_update_try_count = 0
        self.force_update_try_caller = async_call_later(self.hass, START_FORCE_UPDATE_AFTER_COMMAND, self.force_update_loop)

    async def refresh_token(self):
        _LOGGER.debug(f"{DOMAIN} - Refresh token started {self.token.valid_until} {datetime.now()} {self.token.valid_until <= datetime.now().strftime(DATE_FORMAT)}")
        if self.token.valid_until <= datetime.now().strftime(DATE_FORMAT):
            _LOGGER.debug(f"{DOMAIN} - Refresh token expired")
            await self.hass.async_add_executor_job(self.login)
            return True
        return False

    async def start_climate(self):
        await self.hass.async_add_executor_job(self.kia_uvo_api.start_climate, self.token)
        self.force_update_try_count = 0
        self.force_update_try_caller = async_call_later(self.hass, START_FORCE_UPDATE_AFTER_COMMAND, self.force_update_loop)

    async def stop_climate(self):
        await self.hass.async_add_executor_job(self.kia_uvo_api.stop_climate, self.token)
        self.force_update_try_count = 0
        self.force_update_try_caller = async_call_later(self.hass, START_FORCE_UPDATE_AFTER_COMMAND, self.force_update_loop)

    def login(self):
        self.token = self.kia_uvo_api.login()

    def set_last_updated(self):
        m = re.match(
            r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})",
            self.vehicle_data["vehicleStatus"]["time"],
        )
        last_updated = datetime(
            year = int(m.group(1)),
            month = int(m.group(2)),
            day = int(m.group(3)),
            hour = int(m.group(4)),
            minute = int(m.group(5)),
            second = int(m.group(6)),
            tzinfo = TIME_ZONE_EUROPE
        )

        _LOGGER.debug(f"{DOMAIN} - LastUpdated {last_updated} - Timezone {TIME_ZONE_EUROPE}")

        self.last_updated = last_updated
    
    def set_engine_type(self):
        if "dte" in self.vehicle_data["vehicleStatus"]:
            self.engine_type = VEHICLE_ENGINE_TYPE.IC
        else:
            if "lowFuelLight" in self.vehicle_data["vehicleStatus"]:
                self.engine_type = VEHICLE_ENGINE_TYPE.PHEV
            else:
                self.engine_type = VEHICLE_ENGINE_TYPE.EV
        _LOGGER.debug(f"{DOMAIN} - Engine type set {self.engine_type}")

    def get_child_value(self, key):
        value = self.vehicle_data
        for x in key.split("."):
            try:
                value = value[x]
            except:
                try:
                    value = value[int(x)]
                except:
                    value = None
        return value