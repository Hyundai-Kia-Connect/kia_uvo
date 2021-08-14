import logging

from datetime import timedelta, datetime
import push_receiver
import random
import requests
from urllib.parse import parse_qs, urlparse
import uuid
import json

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
        pin: int,
        use_email_with_geocode_api: bool = False,
    ):
        super().__init__(username, password, region, brand, pin, use_email_with_geocode_api)

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
        pin = self.pin

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
        service_status = {}
        service_status = self._get_service_status(token)
        vehicle_status["vehicleStatus"]["odometer"] = {}
        vehicle_status["vehicleStatus"]["odometer"]["unit"]= service_status["serviceStatus"]["currentOdometerUnit"]
        vehicle_status["vehicleStatus"]["odometer"]["value"]= service_status["serviceStatus"]["currentOdometer"]
        _LOGGER.debug(f"{DOMAIN} - Vehicle Status: {vehicle_status}")

        return vehicle_status

    def update_vehicle_status(self, token: Token):
        url = self.API_URL + "rltmvhclsts"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = requests.post(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {response}")
        
    def _get_service_status(self, token: Token):
        url = self.API_URL + "nxtsvc"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = requests.post(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Service status data {response}")
        response = response["result"]["maintenanceInfo"]
        service_status = {}
        service_status["serviceStatus"] = response
        return service_status
        

    def lock_action(self, token: Token, action):
        pin_auth = self.verify_pin(token)
        if action == VEHICLE_LOCK_ACTION.LOCK:
            url = self.API_URL + "drlck"
        else:
            url = self.API_URL + "drulck"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = pin_auth
             
        response = requests.post(url, headers=headers, data=json.dumps({
            "pin": self.pin
        }))
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received lock_action response {response}")

    def start_climate(self, token: Token):
        pass

    def stop_climate(self, token: Token):
        pass

    def start_charge(self, token: Token):
        pass

    def stop_charge(self, token: Token):
        pass
    
    def verify_pin(self, token: Token):

        # https://www.myuvo.ca/tods/api/vrfypin

        print(token.vehicle_id)
        url = self.API_URL + "vrfypin"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
       

        response = requests.post(url, headers=headers, data=json.dumps({
            "pin": self.pin
        }))
        _LOGGER.debug(f"{DOMAIN} - Received Pin validation response {response}")
        result = response.json()['result']

        return result['pAuth']
