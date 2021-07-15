from .const import *

from datetime import tzinfo
from homeassistant.util import dt as dt_util

from .KiaUvoApiImpl import KiaUvoApiImpl
from .KiaUvoApiCA import KiaUvoApiCA
from .KiaUvoApiEU import KiaUvoApiEU

def getImplByRegion(region: int, username: str, password: str, use_email_with_geocode_api: bool = False) -> KiaUvoApiImpl :
    if REGIONS[region] == REGION_CANADA:
        return KiaUvoApiCA(username, password, region, use_email_with_geocode_api)
    elif REGIONS[region] == REGION_EUROPE:
        return KiaUvoApiEU(username, password, use_email_with_geocode_api)

def getTimezoneByRegion(region: int) -> tzinfo:
    if REGIONS[region] == REGION_CANADA:
        return dt_util.DEFAULT_TIME_ZONE
    elif REGIONS[region] == REGION_EUROPE:
        return TIME_ZONE_EUROPE