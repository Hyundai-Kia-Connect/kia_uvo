import logging

from datetime import datetime
import push_receiver
import random
import requests
from urllib.parse import parse_qs, urlparse
import uuid

from .const import *
from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token

_LOGGER = logging.getLogger(__name__)

class KiaUvoApiCA(KiaUvoApiImpl):
    def __init__(self, username: str, password: str, use_email_with_geocode_api: bool = False):
        super().__init__(username, password, use_email_with_geocode_api)

    def login(self) -> Token:
        username = self.username
        password = self.password
    
        ### Sign In with Email and Password and Get Authorization Code ###

        url = KIA_UVO_API_URL_CA + "lgn"
        data = {"loginId": username, "password": password}
        headers = KIA_UVO_API_HEADERS_CA
        response = requests.post(url, json=data, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response.text}")
        response = response.json()
        response = response["result"]
        access_token = response["accessToken"]
        refresh_token = response["refreshToken"]
        _LOGGER.debug(f"{DOMAIN} - Access Token Value {access_token}")
        _LOGGER.debug(f"{DOMAIN} - Refresh Token Value {refresh_token}")

        ### Get Vehicles ###
        url = KIA_UVO_API_URL_CA + "vhcllst"
        headers = KIA_UVO_API_HEADERS_CA
        headers["accessToken"] = access_token
        response = requests.post(url, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {response.text}")
        response = response.json()
        response = response["result"]
        vehicle_name = response["vehicles"][0]["nickname"]
        vehicle_id = response["vehicles"][0]["vehicleId"]
        vehicle_model = response["vehicles"][0]["nickname"]
        vehicle_registration_date = response["vehicles"][0]["enrollmentDate"]

        valid_until = (datetime.now() + timedelta(hours=23)).strftime(DATE_FORMAT)

        token = Token({})
        token.set(
            access_token,
            refresh_token,
            None,
            vehicle_name,
            vehicle_id,
            vehicle_model,
            vehicle_registration_date,
            valid_until,
            "NoStamp",
        )

        return token

    def get_cached_vehicle_status(self, token: Token):
        url = KIA_UVO_API_URL_CA + "lstvhclsts"
        headers = KIA_UVO_API_HEADERS_CA
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = requests.post(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {response}")
        response = response["result"]
        return response["resMsg"]["vehicleStatusInfo"]

    def update_vehicle_status(self, token: Token):
        url = KIA_UVO_API_URL_CA + "rltmvhclsts"
        headers = KIA_UVO_API_HEADERS_CA
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = requests.post(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {response}")

    def lock_action(self, token:Token, action):
        pass

    def start_climate(self, token:Token):
        pass

    def stop_climate(self, token:Token):
        pass

    def start_charge(self, token:Token):
        pass

    def stop_charge(self, token:Token):
        pass
