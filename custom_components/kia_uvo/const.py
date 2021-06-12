import logging

from datetime import timedelta
from dateutil import tz
from enum import Enum

from homeassistant.const import LENGTH_KILOMETERS, LENGTH_MILES

# Configuration Constants
DOMAIN: str = "kia_uvo"
CONF_STORED_CREDENTIALS: str = "stored_credentials"
CONF_SCAN_INTERVAL: str = "scan_interval"
CONF_FORCE_SCAN_INTERVAL: str = "force_scan_interval"
CONF_NO_FORCE_SCAN_HOUR_START: str = "no_force_scan_hour_start"
CONF_NO_FORCE_SCAN_HOUR_FINISH: str = "no_force_scan_hour_finish"
CONF_ENABLE_GEOLOCATION_ENTITY: str = "enable_geolocation_entity"
CONF_USE_EMAIL_WITH_GEOCODE_API: str = "use_email_with_geocode_api"

# I have seen that many people can survice with receiving updates in every 30 minutes. Let's see how KIA will responde
DEFAULT_SCAN_INTERVAL: int = 30
# When vehicle is running/active, it will update its status regularly, so no need to force it. If it has not been running, we will force it every 240 minutes
DEFAULT_FORCE_SCAN_INTERVAL: int = 240
DEFAULT_NO_FORCE_SCAN_HOUR_START: int = 22
DEFAULT_NO_FORCE_SCAN_HOUR_FINISH: int = 6
DEFAULT_ENABLE_GEOLOCATION_ENTITY: bool = False
DEFAULT_USE_EMAIL_WITH_GEOCODE_API: bool = False
TIME_ZONE_EUROPE = tz.gettz('Europe/Berlin')

# Integration Setting Constants
PARALLEL_UPDATES: int = 1
CONFIG_FLOW_VERSION: int = 1
PLATFORMS = ["binary_sensor", "device_tracker", "sensor", "lock"]
TOPIC_UPDATE: str = f"{DOMAIN}_update_{0}"

# KiaUvoApi Constants
KIA_UVO_INVALID_STAMP_RETRY_COUNT = 10
KIA_UVO_USER_AGENT_OK_HTTP: str = "okhttp/3.12.0"
KIA_UVO_USER_AGENT_MOZILLA: str = "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19"
KIA_UVO_ACCEPT_HEADER_ALL: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"


# KiaUvoApiEU Constants
KIA_UVO_BASE_URL_EU: str = "prd.eu-ccapi.kia.com:8080"
KIA_UVO_USER_API_URL_EU: str = "https://" + KIA_UVO_BASE_URL_EU + "/api/v1/user/"
KIA_UVO_SPA_API_URL_EU: str = "https://" + KIA_UVO_BASE_URL_EU + "/api/v1/spa/"
KIA_UVO_CCSP_SERVICE_ID_EU: str = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"
KIA_UVO_GCM_SENDER_ID_EU = 199360397125
KIA_UVO_CLIENT_ID_EU: str = KIA_UVO_CCSP_SERVICE_ID_EU

# KiaUvoApiCA Constants
KIA_UVO_BASE_URL_CA: str = "www.myuvo.ca"
KIA_UVO_API_URL_CA: str = "https://" + KIA_UVO_BASE_URL_CA + "/tods/api/"
KIA_UVO_API_HEADERS_CA = {
    "content-type": "application/json;charset=UTF-8",
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
    "host": KIA_UVO_BASE_URL_CA,
    "origin": "https://" + KIA_UVO_BASE_URL_CA,
    "referer": "https://" + KIA_UVO_BASE_URL_CA + "/login",
    "from": "SPA",
    "language": "0",
    "offset": "0",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    }

# Home Assistant Data Storage Constants
DATA_VEHICLE_INSTANCE: str = "vehicle" #Vehicle Instance
DATA_VEHICLE_LISTENER: str = "vehicle_listener" #Vehicle Topic Update Listener Unsubcribe Caller
DATA_CONFIG_UPDATE_LISTENER: str = "config_update_listener" #Config Options Update Listener Unsubcribe Caller

# Retry Specific Constants
START_FORCE_UPDATE_AFTER_COMMAND: int = 10 #Trigger first force update after a command
INTERVAL_FORCE_UPDATE_AFTER_COMMAND: int = 30 #Consecutive force update calls interval
COUNT_FORCE_UPDATE_AFTER_COMMAND: int = 5 #Number of force update calls after a command

# Sensor Specific Constants
NOT_APPLICABLE: str = "Not Applicable"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S.%f"
DYNAMIC_DISTANCE_UNIT: str = "dynamic_distance_unit"
DISTANCE_UNITS = {1: LENGTH_KILOMETERS, 3: LENGTH_MILES}

REGION_EUROPE = "Europe"
REGION_CANADA = "Canada"
DEFAULT_DISTANCE_UNIT = 1
REGIONS = {1: REGION_EUROPE, 2: REGION_CANADA}
DEFAULT_REGION = 1

class VEHICLE_ENGINE_TYPE(Enum):
    EV = 1
    PHEV = 2
    IC = 3

class VEHICLE_LOCK_ACTION(Enum):
    LOCK = "close"
    UNLOCK = "open"

