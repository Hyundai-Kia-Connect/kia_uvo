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
from .KiaUvoApi import KiaUvoApi

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
            kiaUvoApi = KiaUvoApi()
            token = kiaUvoApi.login(username, password)
        except Exception as ex:
            _LOGGER.error("Exception in kia_uvo login : %s", str(ex))
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