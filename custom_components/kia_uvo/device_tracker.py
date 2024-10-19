"""Device Tracker for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.device_tracker import SourceType
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
        if vehicle.location is not None:
            entities.append(HyundaiKiaConnectTracker(coordinator, vehicle))

    async_add_entities(entities)
    return True


class HyundaiKiaConnectTracker(TrackerEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ):
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_location"
        self._attr_name = f"{vehicle.name} Location"
        self._attr_icon = "mdi:map-marker-outline"

    @property
    def latitude(self):
        return self.vehicle.location_latitude

    @property
    def longitude(self):
        return self.vehicle.location_longitude

    @property
    def source_type(self):
        return SourceType.GPS
