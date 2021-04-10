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
        self.kia_uvo_api = None
        self.token = None

    async def async_step_user(self, user_input = None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if not user_input:
            return self._show_form()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        self.kia_uvo_api = KiaUvoApi(username, password)

        try:
            self.token = await self.hass.async_add_executor_job(self.kia_uvo_api.login)
        except Exception as ex:
            _LOGGER.error(f"{DOMAIN} Exception in kia_uvo login : %s", str(ex))
            return self._show_form({"base": "exception"})

        return self.async_create_entry(
            title = user_input[CONF_USERNAME],
            data = {
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_STORED_CREDENTIALS: vars(self.token)
            }
        )

    @callback
    def _show_form(self, errors = None):
        return self.async_show_form(
            step_id = "user",
            data_schema = self.schema,
            errors = errors if errors else {},
        )