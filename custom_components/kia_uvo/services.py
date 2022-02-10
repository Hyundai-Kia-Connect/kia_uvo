import logging
from typing import Any, cast


from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import ServiceCall, callback, HomeAssistant
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from homeassistant.helpers import device_registry

from .const import DOMAIN

SERVICE_UPDATE = "update"
SERVICE_FORCE_UPDATE = "force_update"
SERVICE_LOCK = "lock"
SERVICE_UNLOCK = "unlock"
SERVICE_STOP_CLIMATE = "stop_climate"
SERVICE_START_CLIMATE = "start_climate"
SERVICE_START_CHARGE = "start_charge"
SERVICE_STOP_CHARGE = "stop_charge"

SUPPORTED_SERVICES = (SERVICE_UPDATE, SERVICE_FORCE_UPDATE, SERVICE_LOCK, SERVICE_UNLOCK, SERVICE_STOP_CLIMATE, SERVICE_START_CLIMATE, SERVICE_START_CHARGE, SERVICE_STOP_CHARGE)

_LOGGER = logging.getLogger(__name__)

@callback
def async_setup_services(hass: HomeAssistant) -> bool:
    """Set up services for Hyundai Kia Connect"""

    async def async_handle_force_update(call):
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_force_update_all()
    

    async def async_handle_update(call):
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_update_all()

    async def async_handle_start_climate(call):
        coordinator = _get_coordinator_from_device(hass, call)
        #await coordinator.async_update_all()

    async def async_handle_stop_climate(call):
        coordinator = _get_coordinator_from_device(hass, call)
        #await coordinator.async_update_all()

    async def async_handle_lock(call):
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_lock_vehicle(call.data[ATTR_DEVICE_ID])

    async def async_handle_unlock(call):
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_unlock_vehicle(call.data[ATTR_DEVICE_ID])

    async def async_handle_start_charge(call):
        coordinator = _get_coordinator_from_device(hass, call)
        #await coordinator.async_update_all()

    async def async_handle_stop_charge(call):
        coordinator = _get_coordinator_from_device(hass, call)
        #await coordinator.async_update_all()
        

    services = {
        SERVICE_FORCE_UPDATE: async_handle_force_update,
        SERVICE_UPDATE: async_handle_update,
        SERVICE_START_CLIMATE: async_handle_start_climate,
        SERVICE_STOP_CLIMATE: async_handle_stop_climate,
        SERVICE_LOCK: async_handle_lock,
        SERVICE_UNLOCK: async_handle_unlock,
        SERVICE_START_CHARGE: async_handle_start_charge,
        SERVICE_STOP_CHARGE: async_handle_stop_charge,
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
    device_entry = device_registry.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
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