import logging

from datetime import datetime
import push_receiver
import random
import requests
import uuid
from urllib.parse import parse_qs, urlparse

from .const import *
from .Token import Token

_LOGGER = logging.getLogger(__name__)

class KiaUvoApiImpl:
    def __init__(self, username: str, password: str, use_email_with_geocode_api: bool = False):
        self.username = username
        self.password = password
        self.use_email_with_geocode_api = use_email_with_geocode_api
        self.stamps = None
    
    def login(self) -> Token:
        pass

    def get_cached_vehicle_status(self, token: Token):
        pass

    def get_geocoded_location(self, lat, lon):
        email_parameter = ""
        if self.use_email_with_geocode_api == True:
            email_parameter = "&email=" + self.username

        url = "https://nominatim.openstreetmap.org/reverse?lat=" + str(lat) + "&lon=" + str(lon) + "&format=json&addressdetails=1&zoom=18" + email_parameter
        response = requests.get(url)
        response = response.json()
        return response

    def update_vehicle_status(self, token: Token):
        pass

    def lock_action(self, token:Token, action):
        pass

    def start_climate(self, token:Token):
        pass

    def stop_climate(self, token:Token):
        pass

    def start_charge(self, token:Token):
        pass

    def stop_charge(self, token:Token):
        pass