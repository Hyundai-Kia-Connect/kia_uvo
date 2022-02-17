import logging

from datetime import timedelta, datetime
import random
import string
import secrets

import pytz
import requests
from requests import Response, RequestException
import time

from .const import (
    DOMAIN,
    DATE_FORMAT,
)
from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token

_LOGGER = logging.getLogger(__name__)


class AuthError(RequestException):
    pass


def request_with_active_session(func):
    def request_with_active_session_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AuthError:
            _LOGGER.debug(f"got invalid session, attempting to repair and resend")
            self = args[0]
            token = kwargs["token"]
            new_token = self.login()
            _LOGGER.debug(
                f"old token:{token.access_token}, new token:{new_token.access_token}"
            )
            token.access_token = new_token.access_token
            token.vehicle_regid = new_token.vehicle_regid
            token.valid_until = new_token.valid_until
            json_body = kwargs.get("json_body", None)
            if json_body is not None and json_body.get("vinKey", None):
                json_body["vinKey"] = [token.vehicle_regid]
            response = func(*args, **kwargs)
            return response

    return request_with_active_session_wrapper


def request_with_logging(func):
    def request_with_logging_wrapper(*args, **kwargs):
        url = kwargs["url"]
        json_body = kwargs.get("json_body")
        if json_body is not None:
            _LOGGER.debug(f"sending {url} request with {json_body}")
        else:
            _LOGGER.debug(f"sending {url} request")
        response = func(*args, **kwargs)
        _LOGGER.debug(f"got response {response.text}")
        response_json = response.json()
        if response_json["status"]["statusCode"] == 0:
            return response
        if (
            response_json["status"]["statusCode"] == 1
            and response_json["status"]["errorType"] == 1
            and response_json["status"]["errorCode"] == 1003
        ):
            _LOGGER.debug(f"error: session invalid")
            raise AuthError
        _LOGGER.error(f"error: unknown error response {response.text}")
        raise RequestException

    return request_with_logging_wrapper


class KiaUvoAPIUSA(KiaUvoApiImpl):
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

        self.supports_soc_range = False

        # Randomly generate a plausible device id on startup
        self.device_id = (
            "".join(
                random.choice(string.ascii_letters + string.digits) for _ in range(22)
            )
            + ":"
            + secrets.token_urlsafe(105)
        )

        self.BASE_URL: str = "api.owners.kia.com"
        self.API_URL: str = "https://" + self.BASE_URL + "/apigw/v1/"

    def api_headers(self) -> dict:
        offset = time.localtime().tm_gmtoff / 60 / 60
        headers = {
            "content-type": "application/json;charset=UTF-8",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9",
            "apptype": "L",
            "appversion": "4.10.0",
            "clientid": "MWAMOBILE",
            "from": "SPA",
            "host": self.BASE_URL,
            "language": "0",
            "offset": str(int(offset)),
            "ostype": "Android",
            "osversion": "11",
            "secretkey": "98er-w34rf-ibf3-3f6h",
            "to": "APIGW",
            "tokentype": "G",
            "user-agent": "okhttp/3.12.1",
        }
        # should produce something like "Mon, 18 Oct 2021 07:06:26 GMT". May require adjusting locale to en_US
        date = datetime.now(tz=pytz.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        headers["date"] = date
        headers["deviceid"] = self.device_id
        return headers

    def authed_api_headers(self, token: Token):
        headers = self.api_headers()
        headers["sid"] = token.access_token
        headers["vinkey"] = token.vehicle_regid
        return headers

    @request_with_active_session
    @request_with_logging
    def post_request_with_logging_and_active_session(
        self, token: Token, url: str, json_body: dict
    ) -> Response:
        headers = self.authed_api_headers(token)
        return requests.post(url, json=json_body, headers=headers)

    @request_with_active_session
    @request_with_logging
    def get_request_with_logging_and_active_session(
        self, token: Token, url: str
    ) -> Response:
        headers = self.authed_api_headers(token)
        return requests.get(url, headers=headers)

    def login(self) -> Token:
        username = self.username
        password = self.password

        # Sign In with Email and Password and Get Authorization Code

        url = self.API_URL + "prof/authUser"

        data = {
            "deviceKey": "",
            "deviceType": 2,
            "userCredential": {"userId": username, "password": password},
        }
        headers = self.api_headers()
        response = requests.post(url, json=data, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response.text}")
        session_id = response.headers.get("sid")
        if not session_id:
            raise Exception(
                f"no session id returned in login. Response: {response.text} headers {response.headers} cookies {response.cookies}"
            )
        _LOGGER.debug(f"got session id {session_id}")

        # Get Vehicles
        url = self.API_URL + "ownr/gvl"
        headers = self.api_headers()
        headers["sid"] = session_id
        response = requests.get(url, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {response.text}")
        response = response.json()
        vehicle_summary = response["payload"]["vehicleSummary"][0]
        vehicle_name = vehicle_summary["nickName"]
        vehicle_id = vehicle_summary["vehicleIdentifier"]
        vehicle_vin = vehicle_summary["vin"]
        vehicle_key = vehicle_summary["vehicleKey"]
        vehicle_model = vehicle_summary["modelName"]
        vehicle_registration_date = vehicle_summary.get("enrollmentDate", "missing")

        valid_until = (datetime.now() + timedelta(hours=1)).strftime(DATE_FORMAT)

        # using vehicle_VIN as device ID
        # using vehicle_key as vehicle_regid

        token = Token({})
        token.set(
            session_id,
            None,
            vehicle_vin,
            vehicle_name,
            vehicle_id,
            vehicle_key,
            vehicle_model,
            vehicle_registration_date,
            valid_until,
            "NoStamp",
        )

        return token

    def get_cached_vehicle_status(self, token: Token):
        url = self.API_URL + "cmm/gvi"

        body = {
            "vehicleConfigReq": {
                "airTempRange": "0",
                "maintenance": "1",
                "seatHeatCoolOption": "0",
                "vehicle": "1",
                "vehicleFeature": "0",
            },
            "vehicleInfoReq": {
                "drivingActivty": "0",
                "dtc": "1",
                "enrollment": "1",
                "functionalCards": "0",
                "location": "1",
                "vehicleStatus": "1",
                "weather": "0",
            },
            "vinKey": [token.vehicle_regid],
        }
        response = self.post_request_with_logging_and_active_session(
            token=token, url=url, json_body=body
        )

        response_body = response.json()
        vehicle_status = response_body["payload"]["vehicleInfoList"][0][
            "lastVehicleInfo"
        ]["vehicleStatusRpt"]["vehicleStatus"]

        vehicle_status["time"] = vehicle_status["syncDate"]["utc"]

        if vehicle_status["batteryStatus"].get("stateOfCharge"):
            vehicle_status["battery"] = {
                "batSoc": vehicle_status["batteryStatus"]["stateOfCharge"],
            }

        if vehicle_status.get("evStatus"):
            vehicle_status["evStatus"]["remainTime2"] = {
                "atc": vehicle_status["evStatus"]["remainChargeTime"][0]["timeInterval"]
            }

        vehicle_status["doorOpen"] = vehicle_status["doorStatus"]
        vehicle_status["trunkOpen"] = vehicle_status["doorStatus"]["trunk"]
        vehicle_status["hoodOpen"] = vehicle_status["doorStatus"]["hood"]

        if vehicle_status.get("tirePressure"):
            vehicle_status["tirePressureLamp"] = {
                "tirePressureLampAll": vehicle_status["tirePressure"]["all"]
            }

        climate_data = vehicle_status["climate"]
        vehicle_status["airCtrlOn"] = climate_data["airCtrl"]
        vehicle_status["defrost"] = climate_data["defrost"]
        vehicle_status["sideBackWindowHeat"] = climate_data["heatingAccessory"][
            "rearWindow"
        ]
        vehicle_status["sideMirrorHeat"] = climate_data["heatingAccessory"][
            "sideMirror"
        ]
        vehicle_status["steerWheelHeat"] = climate_data["heatingAccessory"][
            "steeringWheel"
        ]

        vehicle_status["airTemp"] = climate_data["airTemp"]
        vehicle_status["dte"] = vehicle_status.get("distanceToEmpty", None)
        vehicle_data = {
            "vehicleStatus": vehicle_status,
            "odometer": {
                "value": float(
                    response_body["payload"]["vehicleInfoList"][0]["vehicleConfig"][
                        "vehicleDetail"
                    ]["vehicle"]["mileage"]
                ),
                "unit": 3,
            },
            "nextService": {
                "value": float(
                    response_body["payload"]["vehicleInfoList"][0]["vehicleConfig"][
                        "maintenance"
                    ]["nextServiceMile"]
                ),
                "unit": 3,
            },
            "vehicleLocation": response_body["payload"]["vehicleInfoList"][0][
                "lastVehicleInfo"
            ]["location"],
        }
        return vehicle_data

    def get_location(self, token: Token):
        pass

    def get_pin_token(self, token: Token):
        pass

    def update_vehicle_status(self, token: Token):
        url = self.API_URL + "rems/rvs"
        body = {
            "requestType": 0  # value of 1 would return cached results instead of forcing update
        }
        self.post_request_with_logging_and_active_session(
            token=token, url=url, json_body=body
        )

    def check_last_action_status(self, token: Token):
        url = self.API_URL + "cmm/gts"
        body = {"xid": self.last_action_xid}
        response = self.post_request_with_logging_and_active_session(
            token=token, url=url, json_body=body
        )
        response_json = response.json()
        self.last_action_completed = all(
            v == 0 for v in response_json["payload"].values()
        )
        return self.last_action_completed

    def lock_action(self, token: Token, action):
        _LOGGER.debug(f"Action for lock is: {action}")
        if action == "close":
            url = self.API_URL + "rems/door/lock"
            _LOGGER.debug(f"Calling Lock")
        else:
            url = self.API_URL + "rems/door/unlock"
            _LOGGER.debug(f"Calling unlock")

        response = self.get_request_with_logging_and_active_session(
            token=token, url=url
        )

        self.last_action_xid = response.headers["Xid"]

    def start_climate(
        self, token: Token, set_temp, duration, defrost, climate, heating
    ):
        url = self.API_URL + "rems/start"
        if set_temp < 62:
            set_temp = "LOW"
        elif set_temp > 82:
            set_temp = "HIGH"
        body = {
            "remoteClimate": {
                "airCtrl": climate,
                "airTemp": {
                    "unit": 1,
                    "value": str(set_temp),
                },
                "defrost": defrost,
                "heatingAccessory": {
                    "rearWindow": int(heating),
                    "sideMirror": int(heating),
                    "steeringWheel": int(heating),
                },
                "ignitionOnDuration": {
                    "unit": 4,
                    "value": duration,
                },
            }
        }
        response = self.post_request_with_logging_and_active_session(
            token=token, url=url, json_body=body
        )
        self.last_action_xid = response.headers["Xid"]

    def stop_climate(self, token: Token):
        url = self.API_URL + "rems/stop"
        response = self.get_request_with_logging_and_active_session(
            token=token, url=url
        )
        self.last_action_xid = response.headers["Xid"]

    def start_charge(self, token: Token):
        url = self.API_URL + "evc/charge"
        body = {"chargeRatio": 100}
        response = self.post_request_with_logging_and_active_session(
            token=token, url=url, json_body=body
        )
        self.last_action_xid = response.headers["Xid"]

    def stop_charge(self, token: Token):
        url = self.API_URL + "evc/cancel"
        response = self.get_request_with_logging_and_active_session(
            token=token, url=url
        )
        self.last_action_xid = response.headers["Xid"]

    def set_charge_limits(self, token: Token, ac_limit: int, dc_limit: int):
        url = self.API_URL + "evc/sts"
        body = {
            "targetSOClist": [
                {
                    "plugType": 0,
                    "targetSOClevel": dc_limit,
                },
                {
                    "plugType": 1,
                    "targetSOClevel": ac_limit,
                },
            ]
        }
        response = self.post_request_with_logging_and_active_session(
            token=token, url=url, json_body=body
        )
        self.last_action_xid = response.headers["Xid"]
