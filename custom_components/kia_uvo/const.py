import logging

from enum import Enum
from datetime import timedelta
from dateutil import tz

from homeassistant.const import LENGTH_KILOMETERS, LENGTH_MILES

DOMAIN = "kia_uvo"
CONF_STORED_CREDENTIALS = "stored_credentials"
PARALLEL_UPDATES = 1
CONFIG_FLOW_VERSION = 1

BASE_URL = "prd.eu-ccapi.kia.com:8080"
USER_API_URL = "https://" + BASE_URL + "/api/v1/user/"
SPA_API_URL = "https://" + BASE_URL + "/api/v1/spa/"
CCSP_SERVICE_ID = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"
CLIENT_ID = CCSP_SERVICE_ID
USER_AGENT_OK_HTTP = "okhttp/3.12.0"
USER_AGENT_MOZILLA = "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19"
ACCEPT_HEADER_ALL = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"

DATA_VEHICLE_INSTANCE = "vehicle"
DATA_VEHICLE_LISTENER_SCHEDULE = "vehicle_listener_schedule"
DATA_FORCED_VEHICLE_LISTENER_SCHEDULE = "forced_vehicle_listener_schedule"

PLATFORMS = ["binary_sensor", "device_tracker", "sensor", "lock"]
TOPIC_UPDATE = f"{DOMAIN}_update_{0}"

TIME_ZONE_EUROPE = tz.gettz('Europe/Berlin')

# I have seen that many people can survice with receiving updates in every 30 minutes. Let's see how KIA will responde
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)
# When vehicle is running/active, it will update its status regularly, so no need to force it. If it has not been running, we will force it every 240 minutes
FORCE_SCAN_INTERVAL = timedelta(minutes=240)
NO_FORCE_SCAN_HOUR_START = 22
NO_FORCE_SCAN_HOUR_FINISH = 6

START_FORCE_UPDATE_AFTER_COMMAND = 10
INTERVAL_FORCE_UPDATE_AFTER_COMMAND = 30
COUNT_FORCE_UPDATE_AFTER_COMMAND = 5

NOT_APPLICABLE = "Not Applicable"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
DYNAMIC_DISTANCE_UNIT = "dynamic_distance_unit"
DISTANCE_UNITS = {
    1: LENGTH_KILOMETERS, 
    3: LENGTH_MILES
    }
DEFAULT_DISTANCE_UNIT = DISTANCE_UNITS[1]
UPDATE_LISTENER = "update_listener"


class VEHICLE_ENGINE_TYPE(Enum):
    EV = 1
    PHEV = 2
    IC = 3

