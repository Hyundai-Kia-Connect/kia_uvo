import logging

import re
import requests
from datetime import datetime, timezone

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import *
from .Token import Token
from .KiaUvoApi import KiaUvoApi

_LOGGER = logging.getLogger(__name__)

class Vehicle(object):
    def __init__(self, hass, config_entry, token: Token, kia_uvo_api: KiaUvoApi):
        self._hass = hass
        self._config_entry = config_entry
        self._token = token
        self._kia_uvo_api = kia_uvo_api

        self.name = token.vehicle_name
        self.model = token.vehicle_model
        self.id = token.vehicle_id
        self.registration_date = token.vehicle_registration_date
        self.vehicle_data = {}

        self.last_updated: datetime = datetime.min

        self.topic_update = TOPIC_UPDATE.format(token.vehicle_id)
        _LOGGER.debug(f"{DOMAIN} - Received token into Vehicle Object {vars(token)}")

    async def async_update(self):
        self.vehicle_data = await self._hass.async_add_executor_job(self._kia_uvo_api.get_cached_vehicle_status, self._token)
        self.set_last_updated(self.vehicle_data["vehicleStatus"]["time"])
        async_dispatcher_send(self._hass, self.topic_update)

    async def async_force_update(self):
        await self._hass.async_add_executor_job(self._kia_uvo_api.update_vehicle_status, self._token)
        await self.async_update()

    def refresh_token(self):
        _LOGGER.debug(f"{DOMAIN} - Refresh token started {self._token.valid_until} {datetime.now()}")
        if self._token.valid_until <= datetime.now().strftime(DATE_FORMAT):
            _LOGGER.debug(f"{DOMAIN} - Refresh token expired")
            self._token = self._kia_uvo_api.login()
            return True
        return False

    def set_last_updated(self, update_time):
        m = re.match(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", update_time)
        time = datetime(
            year=int(m.group(1)),
            month=int(m.group(2)),
            day=int(m.group(3)),
            hour=int(m.group(4)),
            minute=int(m.group(5)),
            second=int(m.group(6))
        )
        self.last_updated = time