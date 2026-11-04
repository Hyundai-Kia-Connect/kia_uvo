"""Lock for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
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
    """Set up the door lock from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        entities.append(HyundaiKiaConnectLock(coordinator, vehicle))

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectLock(LockEntity, HyundaiKiaConnectEntity):
    """The vehicle's door lock."""

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the lock."""
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_door_lock"
        self._attr_translation_key = "door_lock"

    @property
    def icon(self) -> str | None:
        """Return the icon for the current lock state."""
        return "mdi:lock" if self.is_locked else "mdi:lock-open-variant"

    @property
    def is_locked(self) -> bool | None:
        """Return True if the doors are locked."""
        return self.vehicle.is_locked

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the doors."""
        await self.coordinator.async_lock_vehicle(self.vehicle.id)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the doors."""
        await self.coordinator.async_unlock_vehicle(self.vehicle.id)
