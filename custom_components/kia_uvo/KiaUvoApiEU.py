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

class KiaUvoApiEU(KiaUvoApiImpl):
    def __init__(self, username: str, password: str, use_email_with_geocode_api: bool = False):
        super().__init__(username, password, use_email_with_geocode_api)

    def get_stamps_from_bluelinky(self) -> list:
        stamps = []
        response = requests.get("https://raw.githubusercontent.com/neoPix/bluelinky-stamps/master/kia.json")
        stampsAsText = response.text
        for stamp in stampsAsText.split("\""):
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
        credentials = push_receiver.register(sender_id = KIA_UVO_GCM_SENDER_ID_EU)
        url = KIA_UVO_SPA_API_URL_EU + "notifications/register"
        payload = {"pushRegId": credentials["gcm"]["token"], "pushType": "GCM", "uuid": str(uuid.uuid4())}

        for i in [0,KIA_UVO_INVALID_STAMP_RETRY_COUNT]:
            stamp = random.choice(self.stamps)
            headers = {
                "ccsp-service-id": KIA_UVO_CCSP_SERVICE_ID_EU,
                "Stamp": stamp,
                "Content-Type": "application/json;charset=UTF-8",
                "Host": KIA_UVO_BASE_URL_EU,
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
                "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
            }

            _LOGGER.debug(f"{DOMAIN} - Get Device ID request {headers} {payload}")
            response = requests.post(url, headers=headers, json=payload)
            response = response.json()
            _LOGGER.debug(f"{DOMAIN} - Get Device ID response {response}")
            if not (response["retCode"] == "F" and response["resCode"] == "4017"):
                break
            _LOGGER.debug(f"{DOMAIN} - Retry count {i} - Invalid stamp {stamp}")

        device_id = response["resMsg"]["deviceId"]
        ### Get Cookies ###

        url = (
            KIA_UVO_USER_API_URL_EU
            + "oauth2/authorize?response_type=code&state=test&client_id="
            + KIA_UVO_CLIENT_ID_EU
            + "&redirect_uri="
            + KIA_UVO_USER_API_URL_EU
            + "oauth2/redirect&lang=en"
        )
        payload = {}
        headers = {
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": KIA_UVO_USER_AGENT_MOZILLA,
            "Accept": KIA_UVO_ACCEPT_HEADER_ALL,
            "X-Requested-With": "com.kia.uvo.eu",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en,en-US;q=0.9",
        }

        session = requests.Session()
        response = session.get(url)
        cookies = session.cookies.get_dict()
        _LOGGER.debug(f"{DOMAIN} - Get cookies {cookies}")

        ### Set Language for Session ###

        url = KIA_UVO_USER_API_URL_EU + "language"
        headers = {"Content-type": "application/json"}
        payload = {"lang": "en"}
        response = requests.post(url, json=payload, headers=headers, cookies=cookies)

        ### Sign In with Email and Password and Get Authorization Code ###

        url = KIA_UVO_USER_API_URL_EU + "signin"
        headers = {"Content-type": "application/json"}
        data = {"email": username, "password": password}
        _LOGGER.debug(f"{DOMAIN} - Sign In Data {data}")
        response = requests.post(url, json=data, headers=headers, cookies=cookies)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response.json()}")
        parsed_url = urlparse(response.json()["redirectUrl"])
        authorization_code = "".join(parse_qs(parsed_url.query)["code"])

        ### Get Access Token ###

        url = KIA_UVO_USER_API_URL_EU + "oauth2/token"
        headers = {
            "Authorization": "Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA==",
            "Stamp": stamp,
            "Content-type": "application/x-www-form-urlencoded",
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        data = (
            "grant_type=authorization_code&redirect_uri=https%3A%2F%2Fprd.eu-ccapi.kia.com%3A8080%2Fapi%2Fv1%2Fuser%2Foauth2%2Fredirect&code="
            + authorization_code
        )
        response = requests.post(url, data=data, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Access Token Response {response}")
        token_type = response["token_type"]
        access_token = token_type + " " + response["access_token"]
        authorization_code = response["refresh_token"]
        _LOGGER.debug(f"{DOMAIN} - Access Token Value {access_token}")

        ### Get Refresh Token ###

        url = KIA_UVO_USER_API_URL_EU + "oauth2/token"
        headers = {
            "Authorization": "Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA==",
            "Stamp": stamp,
            "Content-type": "application/x-www-form-urlencoded",
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        data = (
            "grant_type=refresh_token&redirect_uri=https%3A%2F%2Fwww.getpostman.com%2Foauth2%2Fcallback&refresh_token="
            + authorization_code
        )
        response = requests.post(url, data=data, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Refresh Token Response {response}")
        token_type = response["token_type"]
        refresh_token = token_type + " " + response["access_token"]

        ### Get Vehicles ###
        url = KIA_UVO_SPA_API_URL_EU + "vehicles"
        headers = {
            "Authorization": access_token,
            "Stamp": stamp,
            "ccsp-device-id": device_id,
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
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
        url = KIA_UVO_SPA_API_URL_EU + "vehicles/" + token.vehicle_id + "/status/latest"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {response}")
        return response["resMsg"]["vehicleStatusInfo"]

    def update_vehicle_status(self, token: Token):
        url = KIA_UVO_SPA_API_URL_EU + "vehicles/" + token.vehicle_id + "/status"
        headers = {
            "Authorization": token.refresh_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {response}")

    def lock_action(self, token:Token, action):
        url = KIA_UVO_SPA_API_URL_EU + "vehicles/" + token.vehicle_id + "/control/door"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        payload = {"action": action, "deviceId": token.device_id}
        _LOGGER.debug(f"{DOMAIN} - Lock Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Lock Action Response {response}")

    def start_climate(self, token:Token):
        url = KIA_UVO_SPA_API_URL_EU + "vehicles/" + token.vehicle_id + "/control/temperature"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
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

    def stop_climate(self, token:Token):
        url = KIA_UVO_SPA_API_URL_EU + "vehicles/" + token.vehicle_id + "/control/temperature"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
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

    def start_charge(self, token:Token):
        url = KIA_UVO_SPA_API_URL_EU + "vehicles/" + token.vehicle_id + "/control/charge"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        payload = {
            "action": "start", 
            "deviceId": token.device_id
            }
        _LOGGER.debug(f"{DOMAIN} - Start Charge Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Start Charge Action Response {response}")

    def stop_charge(self, token:Token):
        url = KIA_UVO_SPA_API_URL_EU + "vehicles/" + token.vehicle_id + "/control/charge"
        headers = {
            "Authorization": token.access_token,
            "Stamp": token.stamp,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL_EU,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        payload = {
            "action": "stop", 
            "deviceId": token.device_id
            }
        _LOGGER.debug(f"{DOMAIN} - Stop Charge Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Stop Charge Action Response {response}")
