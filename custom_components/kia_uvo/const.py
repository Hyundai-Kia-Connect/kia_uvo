import logging

from enum import Enum
from datetime import timedelta
from dateutil import tz

from homeassistant.const import LENGTH_KILOMETERS, LENGTH_MILES

DOMAIN: str = "kia_uvo"
CONF_STORED_CREDENTIALS: str = "stored_credentials"
CONF_SCAN_INTERVAL: str = "scan_interval"
CONF_FORCE_SCAN_INTERVAL: str = "force_scan_interval"
CONF_NO_FORCE_SCAN_HOUR_START: str = "no_force_scan_hour_start"
CONF_NO_FORCE_SCAN_HOUR_FINISH: str = "no_force_scan_hour_finish"

PARALLEL_UPDATES: int = 1
CONFIG_FLOW_VERSION: int = 1

BASE_URL: str = "prd.eu-ccapi.kia.com:8080"
USER_API_URL: str = "https://" + BASE_URL + "/api/v1/user/"
SPA_API_URL: str = "https://" + BASE_URL + "/api/v1/spa/"
CCSP_SERVICE_ID: str = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"
CLIENT_ID: str = CCSP_SERVICE_ID
USER_AGENT_OK_HTTP: str = "okhttp/3.12.0"
USER_AGENT_MOZILLA: str = "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19"
ACCEPT_HEADER_ALL: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"

DATA_VEHICLE_INSTANCE: str = "vehicle"
DATA_VEHICLE_LISTENER: str = "vehicle_listener"
DATA_FORCED_VEHICLE_LISTENER: str = "forced_vehicle_listener"
DATA_CONFIG_UPDATE_LISTENER: str = "config_update_listener"

PLATFORMS = ["binary_sensor", "device_tracker", "sensor", "lock"]
TOPIC_UPDATE: str = f"{DOMAIN}_update_{0}"

TIME_ZONE_EUROPE = tz.gettz('Europe/Berlin')

# I have seen that many people can survice with receiving updates in every 30 minutes. Let's see how KIA will responde
DEFAULT_SCAN_INTERVAL = 30
# When vehicle is running/active, it will update its status regularly, so no need to force it. If it has not been running, we will force it every 240 minutes
DEFAULT_FORCE_SCAN_INTERVAL: timedelta = 240
DEFAULT_NO_FORCE_SCAN_HOUR_START: int = 22
DEFAULT_NO_FORCE_SCAN_HOUR_FINISH: int = 6

START_FORCE_UPDATE_AFTER_COMMAND: int = 10
INTERVAL_FORCE_UPDATE_AFTER_COMMAND: int = 30
COUNT_FORCE_UPDATE_AFTER_COMMAND: int = 5

NOT_APPLICABLE: str = "Not Applicable"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S.%f"
DYNAMIC_DISTANCE_UNIT: str = "dynamic_distance_unit"
DISTANCE_UNITS = {
    1: LENGTH_KILOMETERS, 
    3: LENGTH_MILES
    }
DEFAULT_DISTANCE_UNIT = 1



class VEHICLE_ENGINE_TYPE(Enum):
    EV = 1
    PHEV = 2
    IC = 3