import logging
from homeassistant.const import ATTR_DEVICE_ID
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
        #coordinator = hass.data[DOMAIN][config_entry.unique_id]
        #await coordinator.async_update_all()
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
    config_entry_ids = hass.data[DOMAIN].keys()
    if len(config_entry_ids) == 1:
        return hass.data[DOMAIN][config_entry_ids[0]]

    dev_reg = device_registry.async_get_registry(hass)
    device = dev_reg.async_get_device(call.data[ATTR_DEVICE_ID])
    _LOGGER.debug(
        f"Device: {device}"
    )
    config_entry = device.config_entries
    _LOGGER.debug(
        f"Config Entires: {config_entry}"
    )
    return hass.data[DOMAIN][config_entry[0].unique_id]
