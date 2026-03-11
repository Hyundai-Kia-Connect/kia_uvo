"""Button for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import Vehicle

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

FORCE_REFRESH_KEY = "force_refresh"

BUTTON_DESCRIPTIONS: Final[tuple[ButtonEntityDescription, ...]] = (
    ButtonEntityDescription(
        key=FORCE_REFRESH_KEY,
        name="Force Refresh",
        icon="mdi:refresh",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in BUTTON_DESCRIPTIONS:
            entities.append(HyundaiKiaConnectButton(coordinator, description, vehicle))

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectButton(ButtonEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: ButtonEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._description = description
        self._key = description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = description.icon
        self._attr_name = f"{vehicle.name} {description.name}"

    async def async_press(self) -> None:
        if self._key == FORCE_REFRESH_KEY:
            await self.coordinator.async_force_refresh_vehicle(self.vehicle.id)
