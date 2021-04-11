import logging

import uuid
import requests
from urllib.parse import parse_qs, urlparse
from datetime import datetime

from .const import *
from .Token import Token

_LOGGER = logging.getLogger(__name__)


class KiaUvoApi:
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def login(self) -> Token:
        username = self.username
        password = self.password
        ### Get Device Id ###

        url = SPA_API_URL + "notifications/register"
        payload = {"pushRegId": "1", "pushType": "GCM", "uuid": str(uuid.uuid1())}
        headers = {
            "ccsp-service-id": CCSP_SERVICE_ID,
            "Stamp": "9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=",
            "Content-Type": "application/json;charset=UTF-8",
            "Host": BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.post(url, headers=headers, json=payload)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Device ID response {response}")

        device_id = response["resMsg"]["deviceId"]

        ### Get Cookies ###

        url = (
            USER_API_URL
            + "oauth2/authorize?response_type=code&state=test&client_id="
            + CLIENT_ID
            + "&redirect_uri="
            + USER_API_URL
            + "oauth2/redirect&lang=en"
        )
        payload = {}
        headers = {
            "Host": BASE_URL,
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

        session = requests.Session()
        response = session.get(url)
        cookies = session.cookies.get_dict()
        _LOGGER.debug(f"{DOMAIN} - Get cookies {cookies}")

        ### Set Language for Session ###

        url = USER_API_URL + "language"
        headers = {"Content-type": "application/json"}
        payload = {"lang": "en"}
        response = requests.post(url, json=payload, headers=headers, cookies=cookies)

        ### Sign In with Email and Password and Get Authorization Code ###

        url = USER_API_URL + "signin"
        headers = {"Content-type": "application/json"}
        data = {"email": username, "password": password}
        response = requests.post(url, json=data, headers=headers, cookies=cookies)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response.json()}")
        parsed_url = urlparse(response.json()["redirectUrl"])
        authorization_code = "".join(parse_qs(parsed_url.query)["code"])

        ### Get Access Token ###

        url = USER_API_URL + "oauth2/token"
        headers = {
            "Authorization": "Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA==",
            "Stamp": "9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=",
            "Content-type": "application/x-www-form-urlencoded",
            "Host": BASE_URL,
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": USER_AGENT_OK_HTTP,
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

        url = USER_API_URL + "oauth2/token"
        headers = {
            "Authorization": "Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA==",
            "Stamp": "9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=",
            "Content-type": "application/x-www-form-urlencoded",
            "Host": BASE_URL,
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": USER_AGENT_OK_HTTP,
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
        url = SPA_API_URL + "vehicles"
        headers = {
            "Authorization": access_token,
            "Stamp": "9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=",
            "ccsp-device-id": device_id,
            "Host": BASE_URL,
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
        )

        return token

    def get_cached_vehicle_status(self, token: Token):
        url = SPA_API_URL + "vehicles/" + token.vehicle_id + "/status/latest"
        headers = {
            "Authorization": token.access_token,
            "Stamp": "9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=",
            "ccsp-device-id": token.device_id,
            "Host": BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {response}")
        return response["resMsg"]["vehicleStatusInfo"]

    def update_vehicle_status(self, token: Token):
        url = SPA_API_URL + "vehicles/" + token.vehicle_id + "/status"
        headers = {
            "Authorization": token.refresh_token,
            "Stamp": "9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=",
            "ccsp-device-id": token.device_id,
            "Host": BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {response}")