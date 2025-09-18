import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    CONF_USERNAME,
    CONF_REGION,
    CONF_PIN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntry

import hashlib

from .const import (
    DOMAIN,
    CONF_BRAND,
    DEFAULT_PIN,
    BRANDS,
    REGIONS,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_NO_FORCE_REFRESH_HOUR_FINISH,
    CONF_NO_FORCE_REFRESH_HOUR_START,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
)
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NUMBER,
    # Platform.CLIMATE,
]


async def async_setup(hass: HomeAssistant, config_entry: ConfigEntry):
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hyundai / Kia Connect from a config entry."""
    coordinator = HyundaiKiaConnectDataUpdateCoordinator(hass, config_entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed as AuthError:
        raise ConfigEntryAuthFailed(AuthError) from AuthError
    except Exception as ex:
        raise ConfigEntryNotReady(f"Config Not Ready: {ex}")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.unique_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        del hass.data[DOMAIN][config_entry.unique_id]
    if not hass.data[DOMAIN]:
        async_unload_services(hass)
    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    if config_entry.version == 1:
        _LOGGER.debug(f"{DOMAIN} - config data- {config_entry}")
        username = config_entry.data.get(CONF_USERNAME)
        password = config_entry.data.get(CONF_PASSWORD)
        pin = config_entry.data.get(CONF_PIN, DEFAULT_PIN)
        region = config_entry.data.get(CONF_REGION, "")
        brand = config_entry.data.get(CONF_BRAND, "")
        geolocation_enable = config_entry.data.get(CONF_ENABLE_GEOLOCATION_ENTITY, "")
        geolocation_use_email = config_entry.data.get(
            CONF_USE_EMAIL_WITH_GEOCODE_API, ""
        )
        no_force_finish_hour = config_entry.data.get(
            CONF_NO_FORCE_REFRESH_HOUR_FINISH, ""
        )
        no_force_start_hour = config_entry.data.get(
            CONF_NO_FORCE_REFRESH_HOUR_START, ""
        )
        force_refresh_interval = config_entry.data.get(CONF_FORCE_REFRESH_INTERVAL, "")
        scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, "")
        title = f"{BRANDS[brand]} {REGIONS[region]} {username}"
        unique_id = hashlib.sha256(title.encode("utf-8")).hexdigest()
        new_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_PIN: pin,
            CONF_REGION: region,
            CONF_BRAND: brand,
            CONF_ENABLE_GEOLOCATION_ENTITY: geolocation_enable,
            CONF_USE_EMAIL_WITH_GEOCODE_API: geolocation_use_email,
            CONF_NO_FORCE_REFRESH_HOUR_FINISH: no_force_finish_hour,
            CONF_NO_FORCE_REFRESH_HOUR_START: no_force_start_hour,
            CONF_FORCE_REFRESH_INTERVAL: force_refresh_interval,
            CONF_SCAN_INTERVAL: scan_interval,
        }
        registry = hass.helpers.entity_registry.async_get(hass)
        entities = hass.helpers.entity_registry.async_entries_for_config_entry(
            registry, config_entry.entry_id
        )
        for entity in entities:
            registry.async_remove(entity.entity_id)

        hass.config_entries.async_update_entry(
            config_entry, unique_id=unique_id, title=title, data=new_data
        )
        config_entry.version = 2
        _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True
