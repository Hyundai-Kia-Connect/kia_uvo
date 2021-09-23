import logging

from datetime import timedelta, datetime
import json
import push_receiver
import random
import requests
from urllib.parse import parse_qs, urlparse
import uuid

from .const import DOMAIN, BRANDS, BRAND_HYUNDAI, BRAND_KIA, DATE_FORMAT, VEHICLE_LOCK_ACTION
from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token

_LOGGER = logging.getLogger(__name__)


class KiaUvoApiCA(KiaUvoApiImpl):
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

        if BRANDS[brand] == BRAND_KIA:
            self.BASE_URL: str = "www.myuvo.ca"
        elif BRANDS[brand] == BRAND_HYUNDAI:
            self.BASE_URL: str = "www.mybluelink.ca"

        self.API_URL: str = "https://" + self.BASE_URL + "/tods/api/"
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
        }

    def login(self) -> Token:
        username = self.username
        password = self.password

        ### Sign In with Email and Password and Get Authorization Code ###

        url = self.API_URL + "lgn"
        data = {"loginId": username, "password": password}
        headers = self.API_HEADERS
        response = requests.post(url, json=data, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response.text}")
        response = response.json()
        response = response["result"]
        access_token = response["accessToken"]
        refresh_token = response["refreshToken"]
        _LOGGER.debug(f"{DOMAIN} - Access Token Value {access_token}")
        _LOGGER.debug(f"{DOMAIN} - Refresh Token Value {refresh_token}")

        ### Get Vehicles ###
        url = self.API_URL + "vhcllst"
        headers = self.API_HEADERS
        headers["accessToken"] = access_token
        response = requests.post(url, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {response.text}")
        response = response.json()
        response = response["result"]
        vehicle_name = response["vehicles"][0]["nickName"]
        vehicle_id = response["vehicles"][0]["vehicleId"]
        vehicle_model = response["vehicles"][0]["nickName"]
        vehicle_registration_date = response["vehicles"][0].get("enrollmentDate","missing")

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
        # Vehicle Status Call
        url = self.API_URL + "lstvhclsts"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = requests.post(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {response}")
        response = response["result"]["status"]

        vehicle_status = {}
        vehicle_status["vehicleStatus"] = response
        vehicle_status["vehicleStatus"]["time"] = response["lastStatusDate"]

        # Service Status Call
        url = self.API_URL + "nxtsvc"
        response = requests.post(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Service status data {response}")
        response = response["result"]["maintenanceInfo"]

        vehicle_status["odometer"] = {}
        vehicle_status["odometer"]["unit"]= response["currentOdometerUnit"]
        vehicle_status["odometer"]["value"]= response["currentOdometer"]
        vehicle_status["vehicleLocation"] = self.get_location(token)

            
        return vehicle_status

    def get_location(self, token: Token):
        url = self.API_URL + "fndmcr"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = self.get_pin_token(token)

        response = requests.post(url, headers=headers, data=json.dumps({"pin": self.pin}))
        response = response.json()
        
        _LOGGER.debug(f"{DOMAIN} - Get Vehicle Location {response}")

        return response["result"]

    def get_pin_token(self, token: Token):
        url = self.API_URL + "vrfypin"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = requests.post(url, headers=headers, data=json.dumps({"pin": self.pin}))
        _LOGGER.debug(f"{DOMAIN} - Received Pin validation response {response}")
        result = response.json()['result']

        return result['pAuth']

    def update_vehicle_status(self, token: Token):
        url = self.API_URL + "rltmvhclsts"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = requests.post(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {response}")

    def lock_action(self, token: Token, action):
        if action == "close":
            url = self.API_URL + "drlck"
        else:
            url = self.API_URL + "drulck"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = self.get_pin_token(token)

        response = requests.post(url, headers=headers, data=json.dumps({"pin": self.pin}))
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received lock_action response {response}")

    def start_climate(self, token: Token):
        url = self.API_URL + "rmtstrt"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = self.get_pin_token(token)

        response = requests.post(url, headers=headers, data=json.dumps({"setting": {"airCtrl": 0, "defrost": "false", "heating1": 0, "igniOnDuration": 3, "ims": 0}, "pin": self.pin}))
        response = response.json()

        _LOGGER.debug(f"{DOMAIN} - Received start_climate response {response}")


    def stop_climate(self, token: Token):
        url = self.API_URL + "rmtstp"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = self.get_pin_token(token)

        response = requests.post(url, headers=headers, data=json.dumps({"pin": self.pin}))
        response = response.json()

        _LOGGER.debug(f"{DOMAIN} - Received stop_climate response {response}")
        

    def start_charge(self, token: Token):
        pass

    def stop_charge(self, token: Token):
        pass
