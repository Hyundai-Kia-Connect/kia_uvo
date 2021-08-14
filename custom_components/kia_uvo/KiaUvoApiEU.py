import logging

from datetime import timedelta, datetime
import push_receiver
import random
import requests
from urllib.parse import parse_qs, urlparse
import uuid
import traceback

from .const import BRANDS, BRAND_HYUNDAI, BRAND_KIA, DOMAIN, DATE_FORMAT
from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token

_LOGGER = logging.getLogger(__name__)

INVALID_STAMP_RETRY_COUNT = 10
USER_AGENT_OK_HTTP: str = "okhttp/3.12.0"
USER_AGENT_MOZILLA: str = "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19"
ACCEPT_HEADER_ALL: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"


class KiaUvoApiEU(KiaUvoApiImpl):
    def __init__(
        self,
        username: str,
        password: str,
        region: int,
        brand: int,
        use_email_with_geocode_api: bool = False,
        pin: int,
    ):
        super().__init__(username, password, region, brand, use_email_with_geocode_api, pin)

        if BRANDS[brand] == BRAND_KIA:
            self.BASE_DOMAIN: str = "prd.eu-ccapi.kia.com"
            self.CCSP_SERVICE_ID: str = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"
            self.BASIC_AUTHORIZATION: str = (
                "Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA=="
            )
        elif BRANDS[brand] == BRAND_HYUNDAI:
            self.BASE_DOMAIN: str = "prd.eu-ccapi.hyundai.com"
            self.CCSP_SERVICE_ID: str = "6d477c38-3ca4-4cf3-9557-2a1929a94654"
            self.BASIC_AUTHORIZATION: str = "Basic NmQ0NzdjMzgtM2NhNC00Y2YzLTk1NTctMmExOTI5YTk0NjU0OktVeTQ5WHhQekxwTHVvSzB4aEJDNzdXNlZYaG10UVI5aVFobUlGampvWTRJcHhzVg=="

        self.BASE_URL: str = self.BASE_DOMAIN + ":8080"
        self.USER_API_URL: str = "https://" + self.BASE_URL + "/api/v1/user/"
        self.SPA_API_URL: str = "https://" + self.BASE_URL + "/api/v1/spa/"
        self.CLIENT_ID: str = self.CCSP_SERVICE_ID
        self.GCM_SENDER_ID = 199360397125
        self.stamps_url: str = (
            "https://raw.githubusercontent.com/neoPix/bluelinky-stamps/master/"
            + BRANDS[brand].lower()
            + ".json"
        )

    def get_stamps_from_bluelinky(self) -> list:
        stamps = []
        response = requests.get(self.stamps_url)
        stampsAsText = response.text
        for stamp in stampsAsText.split('"'):
            stamp = stamp.strip()
            if len(stamp) == 64:
                stamps.append(stamp)
        return stamps

    def login(self) -> Token:

        if self.stamps is None:
            self.stamps = self.get_stamps_from_bluelinky()

        username = self.username
        password = self.password

        ### test url: https://prd.eu-ccapi.kia.com:8080/web/v1/user/intgmain

        ### Get Device Id ###
        credentials = push_receiver.register(sender_id=self.GCM_SENDER_ID)
        url = self.SPA_API_URL + "notifications/register"
        payload = {
            "pushRegId": credentials["gcm"]["token"],
            "pushType": "GCM",
            "uuid": str(uuid.uuid4()),
        }

        for i in [0, INVALID_STAMP_RETRY_COUNT]:
            stamp = random.choice(self.stamps)
            headers = {
                "ccsp-service-id": self.CCSP_SERVICE_ID,
                "Stamp": stamp,
                "Content-Type": "application/json;charset=UTF-8",
                "Host": self.BASE_URL,
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
                "User-Agent": USER_AGENT_OK_HTTP,
            }

            response = requests.post(url, headers=headers, json=payload)
            response = response.json()
            _LOGGER.debug(f"{DOMAIN} - Get Device ID request {headers} {payload}")
            _LOGGER.debug(f"{DOMAIN} - Get Device ID response {response}")
            if not (response["retCode"] == "F" and response["resCode"] == "4017"):
                break
            _LOGGER.debug(f"{DOMAIN} - Retry count {i} - Invalid stamp {stamp}")

        device_id = response["resMsg"]["deviceId"]

        ### Get Cookies ###
        url = (
            self.USER_API_URL
            + "oauth2/authorize?response_type=code&state=test&client_id="
            + self.CLIENT_ID
            + "&redirect_uri="
            + self.USER_API_URL
            + "oauth2/redirect&lang=en"
        )
        payload = {}
        headers = {
            "Host": self.BASE_URL,
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": USER_AGENT_MOZILLA,
            "Accept": ACCEPT_HEADER_ALL,
            "X-Requested-With": "com.kia.uvo.eu",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en,en-US;q=0.9",
        }

        _LOGGER.debug(f"{DOMAIN} - Get cookies request {url}")
        session = requests.Session()
        response = session.get(url)
        cookies = session.cookies.get_dict()
        _LOGGER.debug(f"{DOMAIN} - Get cookies response {cookies}")

        ### Set Language for Session ###
        url = self.USER_API_URL + "language"
        headers = {"Content-type": "application/json"}
        payload = {"lang": "en"}
        response = requests.post(url, json=payload, headers=headers, cookies=cookies)

        ### Sign In with Email and Password and Get Authorization Code ###
        url = self.USER_API_URL + "signin"
        headers = {"Content-type": "application/json"}
        data = {"email": username, "password": password}
        response = requests.post(url, json=data, headers=headers, cookies=cookies)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response.json()}")
        parsed_url = urlparse(response.json()["redirectUrl"])
        authorization_code = "".join(parse_qs(parsed_url.query)["code"])

        ### Get Access Token ###
        url = self.USER_API_URL + "oauth2/token"
        headers = {
            "Authorization": self.BASIC_AUTHORIZATION,
            "Stamp": stamp,
            "Content-type": "application/x-www-form-urlencoded",
            "Host": self.BASE_URL,
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        data = (
            "grant_type=authorization_code&redirect_uri=https%3A%2F%2F"
            + self.BASE_DOMAIN
            + "%3A8080%2Fapi%2Fv1%2Fuser%2Foauth2%2Fredirect&code="
            + authorization_code
        )
        _LOGGER.debug(f"{DOMAIN} - Get Access Token Data {headers }{data}")
        response = requests.post(url, data=data, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Access Token Response {response}")

        token_type = response["token_type"]
        access_token = token_type + " " + response["access_token"]
        authorization_code = response["refresh_token"]
        _LOGGER.debug(f"{DOMAIN} - Access Token Value {access_token}")

        ### Get Refresh Token ###
        url = self.USER_API_URL + "oauth2/token"
        headers = {
            "Authorization": self.BASIC_AUTHORIZATION,
            "Stamp": stamp,
            "Content-type": "application/x-www-form-urlencoded",
            "Host": self.BASE_URL,
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        data = (
            "grant_type=refresh_token&redirect_uri=https%3A%2F%2Fwww.getpostman.com%2Foauth2%2Fcallback&refresh_token="
            + authorization_code
        )
        _LOGGER.debug(f"{DOMAIN} - Get Refresh Token Data {data}")
        response = requests.post(url, data=data, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Refresh Token Response {response}")
        token_type = response["token_type"]
        refresh_token = token_type + " " + response["access_token"]

        ### Get Vehicles ###
        url = self.SPA_API_URL + "vehicles"
        headers = {
            "Authorization": access_token,
            "Stamp": stamp,
            "ccsp-device-id": device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {response}")
        response = response["resMsg"]
        vehicle_name = response["vehicles"][0]["nickname"]
        vehicle_id = response["vehicles"][0]["vehicleId"]
        vehicle_model = response["vehicles"][0]["vehicleName"]
        vehicle_registration_date = response["vehicles"][0]["regDate"]

        valid_until = (datetime.now() + timedelta(hours=23)).strftime(DATE_FORMAT)

        token = Token({})
        token.set(
            access_token,
            refresh_token,
            device_id,
            vehicle_name,
            vehicle_id,
            vehicle_model,
            vehicle_registration_date,
            valid_until,
            stamp,
        )

        return token

    def get_cached_vehicle_status(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/status/latest"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {response}")
        return response["resMsg"]["vehicleStatusInfo"]

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
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/status"
        headers = {
            "Authorization": token.refresh_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {response}")

    def lock_action(self, token: Token, action):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/door"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {"action": action, "deviceId": token.device_id}
        _LOGGER.debug(f"{DOMAIN} - Lock Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Lock Action Response {response}")

    def start_climate(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/temperature"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {
            "action": "start",
            "hvacType": 0,
            "options": {
                "defrost": True,
                "heating1": 1,
            },
            "tempCode": "10H",
            "unit": "C",
        }
        _LOGGER.debug(f"{DOMAIN} - Start Climate Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Start Climate Action Response {response}")

    def stop_climate(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/temperature"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {
            "action": "stop",
            "hvacType": 0,
            "options": {
                "defrost": True,
                "heating1": 1,
            },
            "tempCode": "10H",
            "unit": "C",
        }
        _LOGGER.debug(f"{DOMAIN} - Stop Climate Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Stop Climate Action Response {response}")

    def start_charge(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/charge"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {"action": "start", "deviceId": token.device_id}
        _LOGGER.debug(f"{DOMAIN} - Start Charge Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Start Charge Action Response {response}")

    def stop_charge(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/charge"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {"action": "stop", "deviceId": token.device_id}
        _LOGGER.debug(f"{DOMAIN} - Stop Charge Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Stop Charge Action Response {response}")
