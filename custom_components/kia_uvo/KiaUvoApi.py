import logging

from datetime import datetime
import requests
from urllib.parse import parse_qs, urlparse
import uuid

from .const import *
from .Token import Token

_LOGGER = logging.getLogger(__name__)

class KiaUvoApi:
    def __init__(self, username: str, password: str, use_email_with_geocode_api: bool = False):
        self.username = username
        self.password = password
        self.use_email_with_geocode_api = use_email_with_geocode_api

    def login(self) -> Token:
        username = self.username
        password = self.password
        
        ### Get Device Id ###

        url = KIA_UVO_SPA_API_URL + "notifications/register"
        payload = {"pushRegId": "1", "pushType": "GCM", "uuid": str(uuid.uuid1())}
        headers = {
            "ccsp-service-id": KIA_UVO_CCSP_SERVICE_ID,
            "Stamp": KIA_UVO_STAMP,
            "Content-Type": "application/json;charset=UTF-8",
            "Host": KIA_UVO_BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        response = requests.post(url, headers=headers, json=payload)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Device ID response {response}")

        device_id = response["resMsg"]["deviceId"]

        ### Get Cookies ###

        url = (
            KIA_UVO_USER_API_URL
            + "oauth2/authorize?response_type=code&state=test&client_id="
            + KIA_UVO_CLIENT_ID
            + "&redirect_uri="
            + KIA_UVO_USER_API_URL
            + "oauth2/redirect&lang=en"
        )
        payload = {}
        headers = {
            "Host": KIA_UVO_BASE_URL,
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

        url = KIA_UVO_USER_API_URL + "language"
        headers = {"Content-type": "application/json"}
        payload = {"lang": "en"}
        response = requests.post(url, json=payload, headers=headers, cookies=cookies)

        ### Sign In with Email and Password and Get Authorization Code ###

        url = KIA_UVO_USER_API_URL + "signin"
        headers = {"Content-type": "application/json"}
        data = {"email": username, "password": password}
        response = requests.post(url, json=data, headers=headers, cookies=cookies)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response.json()}")
        parsed_url = urlparse(response.json()["redirectUrl"])
        authorization_code = "".join(parse_qs(parsed_url.query)["code"])

        ### Get Access Token ###

        url = KIA_UVO_USER_API_URL + "oauth2/token"
        headers = {
            "Authorization": "Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA==",
            "Stamp": KIA_UVO_STAMP,
            "Content-type": "application/x-www-form-urlencoded",
            "Host": KIA_UVO_BASE_URL,
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

        url = KIA_UVO_USER_API_URL + "oauth2/token"
        headers = {
            "Authorization": "Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA==",
            "Stamp": KIA_UVO_STAMP,
            "Content-type": "application/x-www-form-urlencoded",
            "Host": KIA_UVO_BASE_URL,
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
        url = KIA_UVO_SPA_API_URL + "vehicles"
        headers = {
            "Authorization": access_token,
            "Stamp": KIA_UVO_STAMP,
            "ccsp-device-id": device_id,
            "Host": KIA_UVO_BASE_URL,
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
        )

        return token

    def get_cached_vehicle_status(self, token: Token):
        url = KIA_UVO_SPA_API_URL + "vehicles/" + token.vehicle_id + "/status/latest"
        headers = {
            "Authorization": token.access_token,
            "Stamp": KIA_UVO_STAMP,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {response}")
        return response["resMsg"]["vehicleStatusInfo"]

    def get_geocoded_location(self, lat, lon):
        email_parameter = ""
        if self.use_email_with_geocode_api == True:
            email_parameter = "&email=" + self.username

        url = "https://nominatim.openstreetmap.org/reverse?lat=" + str(lat) + "&lon=" + str(lon) + "&format=json&addressdetails=1&zoom=18" + email_parameter
        response = requests.get(url)
        response = response.json()
        return response

    def update_vehicle_status(self, token: Token):
        url = KIA_UVO_SPA_API_URL + "vehicles/" + token.vehicle_id + "/status"
        headers = {
            "Authorization": token.refresh_token,
            "Stamp": KIA_UVO_STAMP,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {response}")

    def lock_action(self, token:Token, action):
        url = KIA_UVO_SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/door"
        headers = {
            "Authorization": token.access_token,
            "Stamp": KIA_UVO_STAMP,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": KIA_UVO_USER_AGENT_OK_HTTP,
        }

        payload = {"action": action, "deviceId": token.device_id}
        _LOGGER.debug(f"{DOMAIN} - Lock Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Lock Action Response {response}")

    def start_climate(self, token:Token):
        url = KIA_UVO_SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/temperature"
        headers = {
            "Authorization": token.access_token,
            "Stamp": KIA_UVO_STAMP,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL,
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
        url = KIA_UVO_SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/temperature"
        headers = {
            "Authorization": token.access_token,
            "Stamp": KIA_UVO_STAMP,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL,
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
        url = KIA_UVO_SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/charge"
        headers = {
            "Authorization": token.access_token,
            "Stamp": KIA_UVO_STAMP,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL,
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
        url = KIA_UVO_SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/charge"
        headers = {
            "Authorization": token.access_token,
            "Stamp": KIA_UVO_STAMP,
            "ccsp-device-id": token.device_id,
            "Host": KIA_UVO_BASE_URL,
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
