from .const import REGIONS, REGION_CANADA, REGION_EUROPE

from .KiaUvoApiImpl import KiaUvoApiImpl
from .KiaUvoApiCA import KiaUvoApiCA
from .KiaUvoApiEU import KiaUvoApiEU


def get_implementation_by_region_brand(
    region: int,
    brand: int,
    username: str,
    password: str,
    pin: int,
    use_email_with_geocode_api: bool = False,
) -> KiaUvoApiImpl:  # pylint: disable=too-many-arguments
    if REGIONS[region] == REGION_CANADA:
        return KiaUvoApiCA(
            username, password, region, brand, pin, use_email_with_geocode_api
        )
    elif REGIONS[region] == REGION_EUROPE:
        return KiaUvoApiEU(
            username, password, region, brand, pin, use_email_with_geocode_api
        )
