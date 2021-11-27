from .const import (
    REGIONS,
    REGION_CANADA,
    REGION_EUROPE,
    REGION_USA,
    BRANDS,
    BRAND_KIA,
    BRAND_HYUNDAI,
)

from .KiaUvoApiImpl import KiaUvoApiImpl
from .KiaUvoApiCA import KiaUvoApiCA
from .KiaUvoApiEU import KiaUvoApiEU
from .KiaUvoAPIUSA import KiaUvoAPIUSA
from .HyundaiBlueLinkAPIUSA import HyundaiBlueLinkAPIUSA

DEFAULT_DISTANCE_UNIT_ARRAY = []


def get_default_distance_unit() -> int:
    return DEFAULT_DISTANCE_UNIT_ARRAY[0]


def get_implementation_by_region_brand(
    region: int,
    brand: int,
    username: str,
    password: str,
    use_email_with_geocode_api: bool = False,
    pin: str = "",
) -> KiaUvoApiImpl:  # pylint: disable=too-many-arguments
    if REGIONS[region] == REGION_CANADA:
        return KiaUvoApiCA(
            username, password, region, brand, use_email_with_geocode_api, pin
        )
    elif REGIONS[region] == REGION_EUROPE:
        return KiaUvoApiEU(
            username, password, region, brand, use_email_with_geocode_api, pin
        )
    elif REGIONS[region] == REGION_USA and BRANDS[brand] == BRAND_HYUNDAI:
        return HyundaiBlueLinkAPIUSA(
            username, password, region, brand, use_email_with_geocode_api, pin
        )
    elif REGIONS[region] == REGION_USA and BRANDS[brand] == BRAND_KIA:
        return KiaUvoAPIUSA(
            username, password, region, brand, use_email_with_geocode_api, pin
        )
