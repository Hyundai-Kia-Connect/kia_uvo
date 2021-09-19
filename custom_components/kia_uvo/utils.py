from .const import REGIONS, REGION_CANADA, REGION_EUROPE

from .KiaUvoApiImpl import KiaUvoApiImpl
from .KiaUvoApiCA import KiaUvoApiCA
from .KiaUvoApiEU import KiaUvoApiEU

def get_implementation_by_region_brand(
    region: int,
    brand: int,
    username: str,
    password: str,
    use_email_with_geocode_api: bool = False,
    pin: str = ""
) -> KiaUvoApiImpl:  # pylint: disable=too-many-arguments
    if REGIONS[region] == REGION_CANADA:
        return KiaUvoApiCA(
            username, password, region, brand, use_email_with_geocode_api, pin
        )
    elif REGIONS[region] == REGION_EUROPE:
        return KiaUvoApiEU(
            username, password, region, brand, use_email_with_geocode_api, pin
        )
