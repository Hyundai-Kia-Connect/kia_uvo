import logging

import re
import requests
from datetime import datetime, timezone

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from homeassistant.helpers.event import async_call_later

from .const import *
from .Token import Token
from .KiaUvoApi import KiaUvoApi

_LOGGER = logging.getLogger(__name__)

class Vehicle(object):
    def __init__(self, hass, config_entry, token: Token, kia_uvo_api: KiaUvoApi):
        self.hass = hass
        self.config_entry = config_entry
        self.token = token
        self.kia_uvo_api = kia_uvo_api

        self.name = token.vehicle_name
        self.model = token.vehicle_model
        self.id = token.vehicle_id
        self.registration_date = token.vehicle_registration_date
        self.vehicle_data = {}
        self.engine_type = None
        self.last_updated: datetime = datetime.min

        self.lock_action_loop = None

        self.topic_update = TOPIC_UPDATE.format(self.id)
        _LOGGER.debug(f"{DOMAIN} - Received token into Vehicle Object {vars(token)}")

    async def update(self):
        self.vehicle_data = await self.hass.async_add_executor_job(self.kia_uvo_api.get_cached_vehicle_status, self.token)
        self.set_last_updated()
        self.set_engine_type()

        async_dispatcher_send(self.hass, self.topic_update)

    async def force_update(self):
        await self.hass.async_add_executor_job(self.kia_uvo_api.update_vehicle_status, self.token)
        await self.update()

    async def force_update_loop(self, _):
        _LOGGER.debug(f"{DOMAIN} - force_update_loop start {self.lock_action_loop_count} {SCAN_AFTER_LOCK_COUNT}")
        if self.lock_action_loop_count == SCAN_AFTER_LOCK_COUNT:
            self.lock_action_loop_count = 0
            if self.lock_action_loop is not None:
                self.lock_action_loop.remove()
                self.lock_action_loop = None
            return

        last_updated = self.last_updated
        _LOGGER.debug(f"{DOMAIN} - force_update_loop last_updated {last_updated}")

        await self.force_update()
        _LOGGER.debug(f"{DOMAIN} - force_update_loop force_update_finished {last_updated} {self.last_updated}")
        if last_updated == self.last_updated:
            self.lock_action_loop_count = self.lock_action_loop_count + 1
            self.lock_action_loop = async_call_later(self.hass, SCAN_AFTER_LOCK_INTERVAL, self.force_update_loop)        

    async def lock_action(self, action):
        await self.hass.async_add_executor_job(self.kia_uvo_api.lock_action, self.token, action)
        self.lock_action_loop_count = 0
        self.lock_action_loop = async_call_later(self.hass, 1, self.force_update_loop)

    async def refresh_token(self):
        _LOGGER.debug(f"{DOMAIN} - Refresh token started {self.token.valid_until} {datetime.now()} {self.token.valid_until <= datetime.now().strftime(DATE_FORMAT)}")
        if self.token.valid_until <= datetime.now().strftime(DATE_FORMAT):
            _LOGGER.debug(f"{DOMAIN} - Refresh token expired")
            await self.hass.async_add_executor_job(self.login)
            return True
        return False

    def login(self):
        self.token = self.kia_uvo_api.login()

    def set_last_updated(self):
        m = re.match(
            r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})",
            self.vehicle_data["vehicleStatus"]["time"],
        )
        self.last_updated = datetime(
            year = int(m.group(1)),
            month = int(m.group(2)),
            day = int(m.group(3)),
            hour = int(m.group(4)),
            minute = int(m.group(5)),
            second = int(m.group(6)),
        )
    
    def set_engine_type(self):
        if "dte" in self.vehicle_data["vehicleStatus"]:
            self.engine_type = VEHICLE_ENGINE_TYPE.IC
        else:
            if "lowFuelLight" in self.vehicle_data["vehicleStatus"]:
                self.engine_type = VEHICLE_ENGINE_TYPE.PHEV
            else:
                self.engine_type = VEHICLE_ENGINE_TYPE.EV
        _LOGGER.debug(f"{DOMAIN} - Engine type set {self.engine_type}")