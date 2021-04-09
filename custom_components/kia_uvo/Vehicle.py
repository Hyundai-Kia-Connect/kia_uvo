import logging

import requests
import re
from datetime import datetime, timezone

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import SPA_API_URL, BASE_URL, USER_AGENT_OK_HTTP, TOPIC_UPDATE
from .Token import Token

_LOGGER = logging.getLogger(__name__)

class Vehicle(object):
    def __init__(self, hass, config_entry, token: Token):
        self._hass = hass
        self._config_entry = config_entry
        self._token = token
        self.vehicle_data = {}
        self.topic_update = TOPIC_UPDATE.format(token.vehicle_id)
        self.last_updated = datetime.min
        _LOGGER.debug(f"Received token {vars(token)}")

    async def async_update(self):
        self.vehicle_data = await self._hass.async_add_executor_job(self.get_cached_vehicle_status)
        async_dispatcher_send(self._hass, self.topic_update)

    def get_cached_vehicle_status(self):
        url = SPA_API_URL + 'vehicles/' + self._token.vehicle_id + '/status/latest'
        headers = {
            'Authorization': self._token.access_token,
            'Stamp': '9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=',
            'ccsp-device-id': self._token.device_id,
            'Host': BASE_URL,
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'User-Agent': USER_AGENT_OK_HTTP
        }

        response = requests.get(url, headers = headers)
        response = response.json()
        _LOGGER.debug(f"Received cached vehicle data {response}")
        self.set_latest_updated(response["resMsg"]["vehicleStatusInfo"]["vehicleStatus"]["time"])
        return response["resMsg"]["vehicleStatusInfo"]

    async def async_force_update(self):
        await self._hass.async_add_executor_job(self.get_vehicle_status)
        self.vehicle_data = await self._hass.async_add_executor_job(self.get_cached_vehicle_status)
        async_dispatcher_send(self._hass, self.topic_update)

    def get_vehicle_status(self):
        url = SPA_API_URL + 'vehicles/' + self._token.vehicle_id + '/status'
        headers = {
            'Authorization': self._token.refresh_token,
            'Stamp': '9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=',
            'ccsp-device-id': self._token.device_id,
            'Host': BASE_URL,
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'User-Agent': USER_AGENT_OK_HTTP
        }

        response = requests.get(url, headers = headers)
        response = response.json()
        _LOGGER.debug(f"Received forced vehicle data {response}")
        #self.set_latest_updated(response["resMsg"]["vehicleStatusInfo"]["vehicleStatus"]["time"])
        #return response["resMsg"]["vehicleStatusInfo"]

    def set_latest_updated(self, update_time):
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