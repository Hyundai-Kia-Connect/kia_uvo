"""Device Tracker for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from typing import cast

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from hyundai_kia_connect_api import Vehicle

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
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        if vehicle.location is not None:
            entities.append(HyundaiKiaConnectTracker(coordinator, vehicle))

    async_add_entities(entities)


PARALLEL_UPDATES = 0


class HyundaiKiaConnectTracker(TrackerEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_location"
        self._attr_translation_key = "location"
        self._attr_icon = "mdi:map-marker-outline"

    @property
    def latitude(self) -> float | None:
        return cast(float | None, self.vehicle.location_latitude)

    @property
    def longitude(self) -> float | None:
        return cast(float | None, self.vehicle.location_longitude)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS
