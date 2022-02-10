import logging
from typing import Any, cast


from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import ServiceCall, callback, HomeAssistant
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from homeassistant.helpers import device_registry
from homeassistant.helpers import entity_registry

from .const import DOMAIN

SERVICE_UPDATE = "update"
SERVICE_FORCE_UPDATE = "force_update"

SUPPORTED_SERVICES = (SERVICE_UPDATE, SERVICE_FORCE_UPDATE)

_LOGGER = logging.getLogger(__name__)

@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Hyundai Kia Connect"""

    async def async_handle_force_update(call):
        _LOGGER.debug(f"Force Update Call: {call.data}")
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_force_update_all()
    

    async def async_handle_update(call):
        coordinator = hass.data[DOMAIN][config_entry.unique_id]
        await coordinator.async_update_all()
        pass

    services = {
        SERVICE_FORCE_UPDATE: async_handle_force_update,
        SERVICE_UPDATE: async_handle_update,
    }
    
    for service in SUPPORTED_SERVICES:
        hass.services.async_register(
            DOMAIN,
            service,
            services[service]
        )

@callback
def async_unload_services(hass) -> None:
    for service in SUPPORTED_SERVICES:
        hass.services.async_remove(DOMAIN, service)



def _get_coordinator_from_device(hass: HomeAssistant, call: ServiceCall) -> HyundaiKiaConnectDataUpdateCoordinator:
    dev_reg = device_registry.async_get(hass)
    device_entry = dev_reg.async_get(call.data[ATTR_DEVICE_ID][0])
    _LOGGER.debug(
        f"Device: {device_entry}"
    )
    config_entry_ids = device_entry.config_entries
    config_entry_id = next(
        (
            config_entry_id
            for config_entry_id in config_entry_ids
            if cast(
                ConfigEntry,
                hass.config_entries.async_get_entry(config_entry_id),
            ).domain
            == DOMAIN
        ),
        None,
    )
    config_entry_unique_id = hass.config_entries.async_get_entry(config_entry_id).unique_id
    return hass.data[DOMAIN][config_entry_unique_id]
