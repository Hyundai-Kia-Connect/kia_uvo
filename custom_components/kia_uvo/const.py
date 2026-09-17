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

# Optional library version override, set from the integration options flow
# (entry.options["library_override"]). Empty = the manifest-pinned version.
# Accepts a bare version ("4.28.0", extras from the manifest are kept), a
# "==" pin ("==4.28.0"), or any pip requirement verbatim (e.g.
# "hyundai_kia_connect_api @ git+https://github.com/...@refs/pull/N/head").
# See README: Runtime library version override.
CONF_LIBRARY_OVERRIDE: str = "library_override"
# hass.data key holding {"entry_id", "spec"} for the override installed in
# this HA session, so the ConfigEntryNotReady retry does not reinstall, the
# entry that applied it can change or clear its own override, and a second
# entry requesting a different version warns instead of fighting over pip.
OVERRIDE_APPLIED_KEY: str = "kia_uvo_library_override_applied"
# hass.data key holding an asyncio.Lock serializing override installs, so two
# config entries starting at once cannot run pip concurrently.
OVERRIDE_LOCK_KEY: str = "kia_uvo_library_override_lock"
LIB_PACKAGE_NAME: str = "hyundai_kia_connect_api"

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
