"""Device Tracker for Hyundai / Kia Connect integration."""
from __future__ import annotations

import logging

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        entities.append(
                LocationTracker(coordinator, config_entry, vehicle)
            )
    async_add_entities(entities)
    return True

class HyundaiKiaConnectLocationTracker(TrackerEntity, HyundaiKiaConnectEntity):
    def __init__(
    self, 
    coordinator: HyundaiKiaConnectDataUpdateCoordinator, 
    config_entry, 
    vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)

    @property
    def latitude(self):
        return self.vehicle.latitude

    @property
    def longitude(self):
        return self.vehicle.longitude

    @property
    def icon(self):
        return "mdi:map-marker-outline"

    @property
    def source_type(self):
        return SOURCE_TYPE_GPS

    @property
    def name(self):
        return f"{self.vehicle.name} Location"

    @property
    def unique_id(self):
        return f"{DOMAIN}_location_{self.vehicle.id}"