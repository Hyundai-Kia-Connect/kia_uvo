"""Constants for the Hyundai / Kia Connect integration."""

from enum import StrEnum

DOMAIN: str = "kia_uvo"

CONF_BRAND: str = "brand"
CONF_FORCE_REFRESH_INTERVAL: str = "force_refresh"
CONF_NO_FORCE_REFRESH_HOUR_START: str = "no_force_refresh_hour_start"
CONF_NO_FORCE_REFRESH_HOUR_FINISH: str = "no_force_refresh_hour_finish"
CONF_ENABLE_GEOLOCATION_ENTITY: str = "enable_geolocation_entity"
CONF_USE_EMAIL_WITH_GEOCODE_API: str = "use_email_with_geocode_api"
CONF_TOKEN: str = "token"

REGION_EUROPE: str = "Europe"
REGION_EUROPE_CCI: str = "Europe (Beta)"
REGION_CANADA: str = "Canada"
REGION_USA: str = "USA"
REGION_CHINA: str = "China"
REGION_AUSTRALIA: str = "Australia"
REGION_INDIA: str = "India"
REGION_NZ: str = "New Zealand"
REGION_BRAZIL: str = "Brazil"
REGIONS = {
    1: REGION_EUROPE,
    2: REGION_CANADA,
    3: REGION_USA,
    4: REGION_CHINA,
    5: REGION_AUSTRALIA,
    6: REGION_INDIA,
    7: REGION_NZ,
    8: REGION_BRAZIL,
    9: REGION_EUROPE_CCI,
}
BRAND_KIA: str = "Kia"
BRAND_HYUNDAI: str = "Hyundai"
BRAND_GENESIS: str = "Genesis"
BRANDS = {1: BRAND_KIA, 2: BRAND_HYUNDAI, 3: BRAND_GENESIS}

CHARGING_CURRENTS = {1: 100, 2: 90, 3: 60}

DEFAULT_PIN: str = ""
DEFAULT_SCAN_INTERVAL: int = 30
DEFAULT_FORCE_REFRESH_INTERVAL: int = 1440
DEFAULT_NO_FORCE_REFRESH_HOUR_START: int = 22
DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH: int = 7
DEFAULT_ENABLE_GEOLOCATION_ENTITY: bool = False
DEFAULT_USE_EMAIL_WITH_GEOCODE_API: bool = False

DYNAMIC_UNIT: str = "dynamic_unit"


class OffPeakChargingMode(StrEnum):
    """Off-peak charging schedule mode.

    Maps to the (charging_enabled, off_peak_charge_only_enabled) pair the API
    expects. Values are the strings exposed in services.yaml so the service
    payload converts directly: ``OffPeakChargingMode(call.data["mode"])``.
    """

    OFF = "off"
    TIME = "time"
    TARGET = "target"


# Kia/Hyundai paint codes, as reported in the vehicle list's outColor.
# Paint codes are shared across markets. Add only codes confirmed by an owner.
EXTERIOR_COLOR_NAMES: dict[str, str] = {
    "EWE": "Pewter Olive",
}
# Trim (carPackageType) codes per region. Region-specific because codes such
# as "GL" are trim names of their own in other markets.
TRIM_NAMES: dict[str, dict[str, str]] = {
    REGION_INDIA: {"GL": "GT Line"},
}
# Cabin fine-dust colour bands (Hyundai/Kia Fine Dust Indicator, PM2.5).
CABIN_AIR_QUALITY_BANDS: dict[int, str] = {
    1: "blue",
    2: "green",
    3: "orange",
    4: "red",
}

# Maintenance item names from the India alert endpoint (itemId) mapped to the
# labels Kia's own app shows. Unmapped items fall back to their itemId.
MAINTENANCE_ITEM_NAMES: dict[str, str] = {
    "Engine oil": "Engine Oil",
    "Oil Filter": "Oil Filter",
    "Tire position change": "Tyre Rotation",
    "Wheel alignment": "Wheel Alignment",
    "Air Cleaner": "Air Cleaner Filter",
    "Antimicrobial filter": "Cabin Air Filter",
    "Cooling water": "Engine Coolant",
    "Fuel filter": "Fuel Filter",
    "Ignition plug": "Spark Plug",
}
