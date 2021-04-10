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
    def __init__(self, hass, config_entry, token: Token):
        self._hass = hass
        self._config_entry = config_entry
        self._token = token
        self._kiaUvoApi = KiaUvoApi()

        self.name = token.vehicle_name
        self.model = token.vehicle_model
        self.id = token.vehicle_id
        self.registration_date = token.vehicle_registration_date
        self.vehicle_data = {}

        self.last_updated = datetime.min

        self.topic_update = TOPIC_UPDATE.format(token.vehicle_id)
        _LOGGER.debug(f"{DOMAIN} - Received token into Vehicle Object {vars(token)}")

    async def async_update(self):
        self.vehicle_data = self._kiaUvoApi.get_cached_vehicle_status(self._token)
        self.set_last_updated(self.vehicle_data["vehicleStatus"]["time"])
        async_dispatcher_send(self._hass, self.topic_update)

    async def async_force_update(self):
        self._kiaUvoApi.update_vehicle_status(self._token)
        self.async_update()

    def refresh_token(self, email, password):
        _LOGGER.debug(f"{DOMAIN} - Refresh token started {self._token.valid_until} {datetime.now()}")
        if self._token.valid_until <= datetime.now():
            _LOGGER.debug(f"{DOMAIN} - Refresh token expired")
            self._token = self._kiaUvoApi.login(email, password)

    def set_last_updated(self, update_time):
        m = re.match(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", update_time)
        time = datetime(
            year=int(m.group(1)),
            month=int(m.group(2)),
            day=int(m.group(3)),
            hour=int(m.group(4)),
            minute=int(m.group(5)),
            second=int(m.group(6)),
            tzinfo=timezone.utc
        )
        self.last_updated = time.isoformat()