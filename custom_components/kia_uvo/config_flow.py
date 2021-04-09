
import logging

import voluptuous as vol
import uuid
import requests
from urllib.parse import parse_qs, urlparse

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import *
from .Token import Token

_LOGGER = logging.getLogger(__name__)

class KiaUvoFlowHandler(config_entries.ConfigFlow, domain = DOMAIN):

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        self.schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str
        })

    async def async_step_user(self, user_input = None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if not user_input:
            return self._show_form()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        try:
            token = self._login(username, password)
        except Exception as ex:
            _LOGGER.error("Exception: %s", str(ex))
            return self._show_form({"base": "exception"})

        return self.async_create_entry(
            title = user_input[CONF_USERNAME],
            data = {
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_STORED_CREDENTIALS: {
                    'access_token': token.access_token,
                    'refresh_token': token.refresh_token,
                    'vehicle_name': token.vehicle_name,
                    'vehicle_id': token.vehicle_id,
                    'device_id': token.device_id,
                    'vehicle_model': token.vehicle_model, 
                    'vehicle_registration_date': token.vehicle_registration_date
                }
            }
        )

    @callback
    def _show_form(self, errors = None):
        return self.async_show_form(
            step_id = "user",
            data_schema = self.schema,
            errors = errors if errors else {},
        )

    def _login(self, username: str, password: str) -> Token:
        ### Get Device Id ###

        url = SPA_API_URL + "notifications/register"
        payload = {"pushRegId":"1","pushType":"GCM","uuid": str(uuid.uuid1())}
        headers = {
            'ccsp-service-id': CCSP_SERVICE_ID,
            'Stamp': '9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=',
            'Content-Type': 'application/json;charset=UTF-8',
            'Host': BASE_URL,
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'User-Agent': USER_AGENT_OK_HTTP
        }

        response = requests.post(url, headers = headers, json = payload)
        response = response.json()
        _LOGGER.debug(f"Get Device ID response {response}")

        device_id = response['resMsg']['deviceId']

        ### Get Cookies ###

        url = USER_API_URL + "oauth2/authorize?response_type=code&state=test&client_id=" + CLIENT_ID + "&redirect_uri=" + USER_API_URL + "oauth2/redirect&lang=en"
        payload = {}
        headers = {
            'Host': BASE_URL,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': USER_AGENT_MOZILLA,
            'Accept': ACCEPT_HEADER_ALL,
            'X-Requested-With': 'com.kia.uvo.eu',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en,en-US;q=0.9'
        }

        session = requests.Session()
        response = session.get(url)
        cookies = session.cookies.get_dict()
        _LOGGER.debug(f"Get cookies {cookies}")

        ### Set Language for Session ###

        url = USER_API_URL + 'language'
        headers = {'Content-type': 'application/json'}
        payload = {"lang": "en"}
        response = requests.post(url, json = payload, headers = headers, cookies = cookies)

        ### Sign In with Email and Password and Get Authorization Code ###

        url = USER_API_URL + 'signin'
        headers = {'Content-type': 'application/json'}
        data = {"email": username,"password": password}
        response = requests.post(url, json = data, headers = headers, cookies = cookies)
        _LOGGER.debug(f"Sign In Response {response.json}")
        parsed_url = urlparse(response.json()['redirectUrl'])
        authorization_code = ''.join(parse_qs(parsed_url.query)['code'])

        ### Get Access Token ###

        url = USER_API_URL + 'oauth2/token'
        headers = {
            'Authorization': 'Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA==',
            'Stamp': '9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=',
            'Content-type': 'application/x-www-form-urlencoded',
            'Host': BASE_URL,
            'Connection': 'close',
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': USER_AGENT_OK_HTTP
        }

        data = 'grant_type=authorization_code&redirect_uri=https%3A%2F%2Fprd.eu-ccapi.kia.com%3A8080%2Fapi%2Fv1%2Fuser%2Foauth2%2Fredirect&code=' + authorization_code
        response = requests.post(url, data = data, headers = headers)
        response = response.json()
        _LOGGER.debug(f"Get Access Token Response {response}")
        token_type = response['token_type']
        access_token = token_type + ' ' + response['access_token']
        authorization_code = response['refresh_token']
        _LOGGER.debug(f"Access Token Value {access_token}")

        ### Get Refresh Token ###

        url = USER_API_URL + 'oauth2/token'
        headers = {
            'Authorization': 'Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA==',
            'Stamp': '9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=',
            'Content-type': 'application/x-www-form-urlencoded',
            'Host': BASE_URL,
            'Connection': 'close',
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': USER_AGENT_OK_HTTP
        }

        data = 'grant_type=refresh_token&redirect_uri=https%3A%2F%2Fwww.getpostman.com%2Foauth2%2Fcallback&refresh_token=' + authorization_code
        response = requests.post(url, data = data, headers = headers)
        response = response.json()
        _LOGGER.debug(f"Get Refresh Token Response {response}")
        token_type = response['token_type']
        refresh_token = token_type + ' ' + response['access_token']

        ### Get Vehicles ###
        url = SPA_API_URL + 'vehicles'
        headers = {
            'Authorization': access_token,
            'Stamp': '9o3mpjuu/h4vH6cwbgTzPD70J+JaprZSWlyFNmfNg2qhql7gngJHhJh9D0kRQd/xRvg=',
            'ccsp-device-id': device_id,
            'Host': BASE_URL,
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'User-Agent': USER_AGENT_OK_HTTP
        }

        response = requests.get(url, headers = headers).json()
        _LOGGER.debug(f"Get Vehicles Response {response}")
        response = response["resMsg"]
        vehicle_name = response["vehicles"][0]["nickname"]
        vehicle_id = response["vehicles"][0]["vehicleId"]
        vehicle_model = response["vehicles"][0]["vehicleName"]
        vehicle_registration_date = response["vehicles"][0]["regDate"]

        return Token(access_token, refresh_token, device_id, vehicle_name, vehicle_id, vehicle_model, vehicle_registration_date)

