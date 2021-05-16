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
CONF_USE_EMAIL_WITH_GEOCODE_API: str = "use_email_with_geocode_api"

# I have seen that many people can survice with receiving updates in every 30 minutes. Let's see how KIA will responde
DEFAULT_SCAN_INTERVAL: int = 30
# When vehicle is running/active, it will update its status regularly, so no need to force it. If it has not been running, we will force it every 240 minutes
DEFAULT_FORCE_SCAN_INTERVAL: int = 240
DEFAULT_NO_FORCE_SCAN_HOUR_START: int = 22
DEFAULT_NO_FORCE_SCAN_HOUR_FINISH: int = 6
DEFAULT_USE_EMAIL_WITH_GEOCODE_API: bool = False
TIME_ZONE_EUROPE = tz.gettz('Europe/Berlin')

# Integration Setting Constants
PARALLEL_UPDATES: int = 1
CONFIG_FLOW_VERSION: int = 1
PLATFORMS = ["binary_sensor", "device_tracker", "sensor", "lock"]
TOPIC_UPDATE: str = f"{DOMAIN}_update_{0}"

# KiaUvoApi Constants
KIA_UVO_BASE_URL: str = "prd.eu-ccapi.kia.com:8080"
KIA_UVO_USER_API_URL: str = "https://" + KIA_UVO_BASE_URL + "/api/v1/user/"
KIA_UVO_SPA_API_URL: str = "https://" + KIA_UVO_BASE_URL + "/api/v1/spa/"
KIA_UVO_CCSP_SERVICE_ID: str = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"
KIA_UVO_CLIENT_ID: str = KIA_UVO_CCSP_SERVICE_ID
KIA_UVO_USER_AGENT_OK_HTTP: str = "okhttp/3.12.0"
KIA_UVO_USER_AGENT_MOZILLA: str = "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19"
KIA_UVO_ACCEPT_HEADER_ALL: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"

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
DEFAULT_DISTANCE_UNIT = 1
class VEHICLE_ENGINE_TYPE(Enum):
    EV = 1
    PHEV = 2
    IC = 3

class VEHICLE_LOCK_ACTION(Enum):
    LOCK = "close"
    UNLOCK = "open"