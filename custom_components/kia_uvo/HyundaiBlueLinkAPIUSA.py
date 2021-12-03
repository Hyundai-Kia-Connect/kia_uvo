import logging

import time
from datetime import timedelta, datetime
import json
import push_receiver
import random
import requests
from urllib.parse import parse_qs, urlparse
import uuid
import time
import curlify

from .const import (
    DOMAIN,
    BRANDS,
    BRAND_HYUNDAI,
    BRAND_KIA,
    DATE_FORMAT,
    VEHICLE_LOCK_ACTION,
)
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
        super().__init__(
            username, password, region, brand, use_email_with_geocode_api, pin
        )

        self.BASE_URL: str = "api.telematics.hyundaiusa.com"
        self.LOGIN_API: str = "https://" + self.BASE_URL + "/v2/ac/"
        self.API_URL: str = "https://" + self.BASE_URL + "/ac/v2/"

        ts = time.time()
        utc_offset = (
            datetime.fromtimestamp(ts) - datetime.utcfromtimestamp(ts)
        ).total_seconds()
        utc_offset_hours = int(utc_offset / 60 / 60)

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
            "to": "ISS",
            "language": "0",
            "offset": str(utc_offset_hours),
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "refresh": "false",
            "encryptFlag": "false",
            "brandIndicator": "H",
            "gen": "2",
            "username": self.username,
            "blueLinkServicePin": self.pin,
            "client_id": "m66129Bb-em93-SPAHYN-bZ91-am4540zp19920",
            "clientSecret": "v558o935-6nne-423i-baa8",
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
        response = self.get_vehicle(access_token)
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {response.text}")
        vehicle_details = response["enrolledVehicleDetails"][0]["vehicleDetails"]
        vehicle_name = vehicle_details["nickName"]
        vehicle_id = vehicle_details["vin"]
        vehicle_regid = vehicle_details["regid"]
        _LOGGER.debug(f"{DOMAIN} - vehicle_regid={vehicle_regid}")
        vehicle_model = vehicle_details["modelCode"]
        vehicle_registration_date = vehicle_details["enrollmentDate"]

        valid_until = (datetime.now() + timedelta(seconds=expires_in)).strftime(
            DATE_FORMAT
        )

        token = Token({})
        token.set(
            access_token,
            refresh_token,
            None,
            vehicle_name,
            vehicle_id,
            vehicle_regid,
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

        vehicle_status["vehicleStatus"]["dateTime"] = (
            vehicle_status["vehicleStatus"]["dateTime"]
            .replace("-", "")
            .replace("T", "")
            .replace(":", "")
            .replace("Z", "")
        )
        vehicle_status["vehicleStatus"]["time"] = vehicle_status["vehicleStatus"][
            "dateTime"
        ]
        vehicle_status["vehicleStatus"]["date"] = vehicle_status["vehicleStatus"][
            "dateTime"
        ]
        vehicle_status["vehicleStatus"]["doorLock"] = vehicle_status["vehicleStatus"][
            "doorLockStatus"
        ]
        vehicle_status["vehicleLocation"] = vehicle_status["vehicleStatus"][
            "vehicleLocation"
        ]
        if vehicle_status["vehicleStatus"].get("tirePressureLamp"):
            vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureLampAll"
            ] = vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureWarningLampAll"
            ]
            vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureLampFL"
            ] = vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureWarningLampFrontLeft"
            ]
            vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureLampFR"
            ] = vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureWarningLampFrontRight"
            ]
            vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureLampRR"
            ] = vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureWarningLampRearRight"
            ]
            vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureLampRL"
            ] = vehicle_status["vehicleStatus"]["tirePressureLamp"][
                "tirePressureWarningLampRearLeft"
            ]
        # Get Odomoter Details
        response = self.get_vehicle(token.access_token)
        vehicle_status["odometer"] = {}
        vehicle_status["odometer"]["unit"] = 3
        vehicle_status["odometer"]["value"] = response["enrolledVehicleDetails"][0][
            "vehicleDetails"
        ]["odometer"]
        return vehicle_status

    def get_location(self, token: Token):
        pass

    def get_vehicle(self, access_token):
        username = self.username
        password = self.password

        url = self.API_URL + "enrollment/details/" + username
        headers = self.API_HEADERS
        headers["accessToken"] = access_token
        response = requests.get(url, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {response}")
        response = response.json()

        return response

    def get_pin_token(self, token: Token):
        pass

    def update_vehicle_status(self, token: Token):
        pass

    def lock_action(self, token: Token, action):
        _LOGGER.debug(f"{DOMAIN} - Action for lock is: {action}")

        if action == "close":
            url = self.API_URL + "rcs/rdo/off"
            _LOGGER.debug(f"{DOMAIN} - Calling Lock")
        else:
            url = self.API_URL + "rcs/rdo/on"
            _LOGGER.debug(f"{DOMAIN} - Calling unlock")

        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vin"] = token.vehicle_id
        headers["registrationId"] = token.vehicle_regid
        headers["APPCLOUD-VIN"] = token.vehicle_id

        data = {"userName": self.username, "vin": token.vehicle_id}
        response = requests.post(url, headers=headers, json=data)
        # response_headers = response.headers
        # response = response.json()
        # action_status = self.check_action_status(token, headers["pAuth"], response_headers["transactionId"])

        # _LOGGER.debug(f"{DOMAIN} - Received lock_action response {action_status}")
        _LOGGER.debug(
            f"{DOMAIN} - Received lock_action response status code: {response.status_code}"
        )
        _LOGGER.debug(f"{DOMAIN} - Received lock_action response: {response.text}")

    def start_climate(
        self, token: Token, set_temp, duration, defrost, climate, heating
    ):
        _LOGGER.debug(f"{DOMAIN} - Start engine..")

        url = self.API_URL + "rcs/rsc/start"

        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vin"] = token.vehicle_id
        headers["registrationId"] = token.vehicle_regid
        _LOGGER.debug(f"{DOMAIN} - Start engine headers: {headers}")

        data = {
            "Ims": 0,
            "airCtrl": int(climate),
            "airTemp": {"unit": 1, "value": set_temp},
            "defrost": defrost,
            "heating1": int(heating),
            "igniOnDuration": duration,
            # "seatHeaterVentInfo": None,
            "username": self.username,
            "vin": token.vehicle_id,
        }
        _LOGGER.debug(f"{DOMAIN} - Start engine data: {data}")

        response = requests.post(url, json=data, headers=headers)

        # _LOGGER.debug(f"{DOMAIN} - Start engine curl: {curlify.to_curl(response.request)}")
        _LOGGER.debug(
            f"{DOMAIN} - Start engine response status code: {response.status_code}"
        )
        _LOGGER.debug(f"{DOMAIN} - Start engine response: {response.text}")

    def stop_climate(self, token: Token):
        _LOGGER.debug(f"{DOMAIN} - Stop engine..")

        url = self.API_URL + "rcs/rsc/stop"

        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vin"] = token.vehicle_id
        headers["registrationId"] = token.vehicle_regid

        _LOGGER.debug(f"{DOMAIN} - Stop engine headers: {headers}")

        response = requests.post(url, headers=headers)
        _LOGGER.debug(
            f"{DOMAIN} - Stop engine response status code: {response.status_code}"
        )
        _LOGGER.debug(f"{DOMAIN} - Stop engine response: {response.text}")

    def start_charge(self, token: Token):
        pass

    def stop_charge(self, token: Token):
        pass
