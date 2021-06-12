from .const import *

from .KiaUvoApiImpl import KiaUvoApiImpl
from .KiaUvoApiCA import KiaUvoApiCA
from .KiaUvoApiEU import KiaUvoApiEU

def getImplByRegion(region: int, username: str, password: str, use_email_with_geocode_api: bool = False) -> KiaUvoApiImpl :
    if REGIONS[region] == REGION_CANADA:
        return KiaUvoApiCA(username, password, use_email_with_geocode_api)
    elif REGIONS[region] == REGION_EUROPE:
        return KiaUvoApiEU(username, password, use_email_with_geocode_api)