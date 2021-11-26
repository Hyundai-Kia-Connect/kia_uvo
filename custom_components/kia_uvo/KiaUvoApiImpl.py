import logging

import requests

from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
)

from .const import *
from .Token import Token
import time

_LOGGER = logging.getLogger(__name__)


class KiaUvoApiImpl:
    def __init__(
        self,
        hass,
        username: str,
        password: str,
        region: int,
        brand: int,
        use_email_with_geocode_api: bool = False,
        pin: str = "",
    ):
        self.hass = hass
        self.username = username
        self.password = password
        self.pin = pin
        self.use_email_with_geocode_api = use_email_with_geocode_api
        self.stamps = None
        self.region = region
        self.brand = brand

        self.last_action_tracked = False
        self.last_action_xid = None
        self.last_action_completed = False
        self.last_action_name = None
        self.last_action_start_time = None

        self.supports_soc_range = True

    def login(self) -> Token:
        pass

    def get_cached_vehicle_status(self, token: Token):
        pass

    def check_last_action_status(self, token: Token):
        pass

    def get_geocoded_location(self, lat, lon):
        email_parameter = ""
        if self.use_email_with_geocode_api == True:
            email_parameter = "&email=" + self.username

        url = (
            "https://nominatim.openstreetmap.org/reverse?lat="
            + str(lat)
            + "&lon="
            + str(lon)
            + "&format=json&addressdetails=1&zoom=18"
            + email_parameter
        )
        response = requests.get(url)
        response = response.json()
        return response

    def update_vehicle_status(self, token: Token):
        pass

    def lock_action(self, token: Token, action):
        pass

    def start_climate(
        self, token: Token, set_temp, duration, defrost, climate, heating
    ):
        pass

    def stop_climate(self, token: Token):
        pass

    def start_charge(self, token: Token):
        pass

    def stop_charge(self, token: Token):
        pass

    def set_charge_limits(self, token: Token, ac_limit: int, dc_limit: int):
        pass

    def get_timezone_by_region(self) -> tzinfo:
        if REGIONS[self.region] == REGION_CANADA:
            return dt_util.UTC
        elif REGIONS[self.region] == REGION_EUROPE:
            return TIME_ZONE_EUROPE
        elif REGIONS[self.region] == REGION_USA:
            return dt_util.UTC

    def get_temperature_range_by_region(self):
        if REGIONS[self.region] == REGION_CANADA:
            return CA_TEMP_RANGE
        elif REGIONS[self.region] == REGION_EUROPE:
            return EU_TEMP_RANGE
        elif REGIONS[self.region] == REGION_USA:
            return USA_TEMP_RANGE

    def action_status_starting(self, action_name):
        if self.last_action_tracked:
            if self.action_status_in_progress():
                if self.last_action_start_time + FIVE_MINUTES_IN_SECONDS < time.time():
                    self.action_status_completed()
                    # assume exception occurred and release old locks
                else:
                    raise RuntimeError(
                        f"API Action already in progress {self.last_action_name}"
                    )
            self.last_action_name = action_name
            self.last_action_start_time = time.time()
            self._action_status_update()

    def action_status_in_progress(self):
        if self.last_action_tracked:
            return not self.last_action_completed and self.last_action_name is not None
        return False

    def action_status_completed(self):
        self.last_action_xid = None
        self.last_action_completed = True
        self.last_action_name = None
        self._action_status_update()

    def _action_status_update(self):
        async_dispatcher_send(self.hass, TOPIC_UPDATE.format(f"API-AIP"))
