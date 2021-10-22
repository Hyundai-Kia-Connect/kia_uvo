import logging

from datetime import timedelta, datetime
import json
import push_receiver
import random
import requests
from urllib.parse import parse_qs, urlparse
import uuid
import time

from .const import DOMAIN, BRANDS, BRAND_HYUNDAI, BRAND_KIA, DATE_FORMAT, VEHICLE_LOCK_ACTION
from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token

_LOGGER = logging.getLogger(__name__)


class HyundaiBlueLinkAPIUSA(KiaUvoApiImpl):
    def __init__(
        self,
        username: str,
        password: str,
        region: int,
        brand: int,
        use_email_with_geocode_api: bool = False,
        pin: str = "",
    ):
        super().__init__(username, password, region, brand, use_email_with_geocode_api, pin)


        self.BASE_URL: str = "api.telematics.hyundaiusa.com"
        self.LOGIN_API: str = "https://" + self.BASE_URL + "/v2/ac/"
        self.API_URL: str = "https://" + self.BASE_URL + "/ac/v2/"

        self.old_vehicle_status = {}
        self.API_HEADERS = {
            "content-type": "application/json;charset=UTF-8",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
            "host": self.BASE_URL,
            "origin": "https://" + self.BASE_URL,
            "referer": "https://" + self.BASE_URL + "/login",
            "from": "SPA",
            "language": "0",
            "offset": "0",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "refresh": "false",
            "client_id": "m66129Bb-em93-SPAHYN-bZ91-am4540zp19920",
            "clientSecret": "v558o935-6nne-423i-baa8"
        }

        _LOGGER.debug(f"{DOMAIN} - initial API headers: {self.API_HEADERS}")

    def login(self) -> Token:
        username = self.username
        password = self.password

        ### Sign In with Email and Password and Get Authorization Code ###

        url = self.LOGIN_API + "oauth/token"

        data = {"username": username, "password": password}
        headers = self.API_HEADERS
        response = requests.post(url, json=data, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response.text}")
        response = response.json()
        access_token = response["access_token"]
        refresh_token = response["refresh_token"]
        expires_in = float(response["expires_in"])
        _LOGGER.debug(f"{DOMAIN} - Access Token Value {access_token}")
        _LOGGER.debug(f"{DOMAIN} - Refresh Token Value {refresh_token}")

        ### Get Vehicles ###
        url = self.API_URL + "enrollment/details/" + username
        headers = self.API_HEADERS
        headers["accessToken"] = access_token
        response = requests.get(url, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {response.text}")
        response = response.json()
        vehicle_details = response["enrolledVehicleDetails"][0]["vehicleDetails"]
        vehicle_name = vehicle_details["nickName"]
        vehicle_id = vehicle_details["vin"]
        vehicle_model = vehicle_details["modelCode"]
        vehicle_registration_date = vehicle_details["enrollmentDate"]

        valid_until = (datetime.now() + timedelta(seconds=expires_in)).strftime(DATE_FORMAT)

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

        _LOGGER.debug(f"{DOMAIN} - updated API headers: {self.API_HEADERS}")

        return token

    def get_cached_vehicle_status(self, token: Token):
        # Vehicle Status Call
        url = self.API_URL + "rcs/rvs/vehicleStatus"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vin"] = token.vehicle_id

        _LOGGER.debug(f"{DOMAIN} - using API headers: {self.API_HEADERS}")

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {response}")

        vehicle_status = {}
        vehicle_status["vehicleStatus"] = response["vehicleStatus"]

        vehicle_status["vehicleStatus"]["dateTime"] = vehicle_status["vehicleStatus"]["dateTime"].replace("-", "").replace("T", "").replace(":", "").replace("Z", "")
        vehicle_status["vehicleStatus"]["time"] = vehicle_status["vehicleStatus"]["dateTime"]
        vehicle_status["vehicleStatus"]["date"] = vehicle_status["vehicleStatus"]["dateTime"]
        vehicle_status["vehicleStatus"]["doorLock"] = vehicle_status["vehicleStatus"]["doorLockStatus"]

        return vehicle_status
        
    def get_location(self, token: Token):
        pass
    def get_pin_token(self, token: Token):
        pass
    def update_vehicle_status(self, token: Token):
        pass

    def lock_action(self, token: Token, action):
        pass

    def start_climate(self, token: Token, set_temp, duration, defrost, climate, heating):
        pass

    def stop_climate(self, token: Token):
        pass
    def check_action_status(self, token: Token, pAuth, transactionId):
        pass
    def start_charge(self, token: Token):
        pass

    def stop_charge(self, token: Token):
        pass
