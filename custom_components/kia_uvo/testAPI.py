import logging

from datetime import timedelta, datetime
import json
import requests

from .const import (
    DOMAIN,
    BRANDS,
    BRAND_HYUNDAI,
    BRAND_KIA,
    DATE_FORMAT,
)
from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token

_LOGGER = logging.getLogger(__name__)

# set class to the one you want to use it for, rename file to that region and make sure it matches.
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

        self.last_action_tracked = True
        self.last_action_xid = None
        self.last_action_completed = False
        self.last_action_pin_auth = None

        if BRANDS[brand] == BRAND_KIA:
            self.BASE_URL: str = "kiaconnect.ca"
        elif BRANDS[brand] == BRAND_HYUNDAI:
            self.BASE_URL: str = "www.mybluelink.ca"

    def login(self) -> Token:

        response = '{"valid_until": "2021-12-10 18:53:33.708376", "access_token": "test==", "refresh_token": "refresh==", "device_id": "", "vehicle_name": "Test Car", "vehicle_id": "Testcar123", "vehicle_regid": "", "vehicle_model": "New Car", "vehicle_registration_date": "missing", "stamp": "NoStamp"}'
        response = json.loads(response)
        valid_until = datetime.now() + timedelta(minutes=15)
        valid_until = valid_until.strftime("%m-%d-%Y %H:%M:%S")
        token = Token({})
        token.set(
            response["access_token"],
            response["refresh_token"],
            None,
            response["vehicle_name"]+self.username,
            response["vehicle_id"]+self.username,
            None,
            self.username,
            response["vehicle_registration_date"],
            valid_until,
            "NoStamp",
        )
        _LOGGER.debug(f"{DOMAIN} - Token test: {token}")

        return token

    def get_cached_vehicle_status(self, token: Token):
        vehicle_status = '{"responseHeader": {"responseCode": 0, "responseDesc": "Success"}, "result": {"status": {"lastStatusDate": "20211203032102", "airCtrlOn": "False", "engine": "False", "doorLock": "True", "doorOpen": {"frontLeft": 0, "frontRight": 0, "backLeft": 0, "backRight": 0}, "trunkOpen": "False", "airTempUnit": "C", "airTemp": {"value": "01H", "unit": 0}, "defrost": "False", "lowFuelLight": "False", "acc": "False", "hoodOpen": "False", "transCond": "True", "dte": {}, "tirePressureLamp": {}, "battery": {"batSoc": 58, "batSignalReferenceValue": {}}, "remoteIgnition": "True", "seatHeaterVentInfo": {}, "sleepModeCheck": "False", "lampWireStatus": {"headLamp": {}, "stopLamp": {}, "turnSignalLamp": {}}, "windowOpen": {}, "engineRuntime": {}}}}'
        vehicle_status = json.loads(vehicle_status)
        vehicle_status["vehicleStatus"] = vehicle_status["result"]["status"]
        vehicle_status["vehicleStatus"]["time"] = vehicle_status["vehicleStatus"][
            "lastStatusDate"
        ]
        _LOGGER.debug(f"{DOMAIN} - test Car: {vehicle_status}")
        return vehicle_status

    def get_location(self, token: Token):
        pass

    def get_pin_token(self, token: Token):
        pass

    def update_vehicle_status(self, token: Token):
        pass

    def lock_action(self, token: Token, action):
        pass

    def start_climate(self, token: Token):
        pass

    def start_climate_ev(self, token: Token):
        pass

    def stop_climate(self, token: Token):
        pass

    def stop_climate_ev(self, token: Token):
        pass

    def check_last_action_status(self, token: Token):
        pass

    def start_charge(self, token: Token):
        pass

    def stop_charge(self, token: Token):
        pass
