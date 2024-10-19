"""Lock for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
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
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        entities.append(HyundaiKiaConnectLock(coordinator, vehicle))

    async_add_entities(entities)
    return True


class HyundaiKiaConnectLock(LockEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ):
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_door_lock"
        self._attr_name = f"{vehicle.name} Door Lock"

    @property
    def icon(self):
        return "mdi:lock" if self.is_locked else "mdi:lock-open-variant"

    @property
    def is_locked(self):
        return getattr(self.vehicle, "is_locked")

    async def async_lock(self, **kwargs):
        await self.coordinator.async_lock_vehicle(self.vehicle.id)

    async def async_unlock(self, **kwargs):
        await self.coordinator.async_unlock_vehicle(self.vehicle.id)
