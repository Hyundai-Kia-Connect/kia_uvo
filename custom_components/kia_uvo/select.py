"""Select for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import EntityCategory

from hyundai_kia_connect_api import Vehicle

from .const import CHARGING_CURRENTS, DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

CHARGING_CURRENT_OPTIONS = {
    1: "100%",
    2: "90%",
    3: "60%",
}

CHARGING_CURRENT_REVERSE = {v: k for k, v in CHARGING_CURRENT_OPTIONS.items()}


SELECT_DESCRIPTIONS: Final[tuple[SelectEntityDescription, ...]] = (
    SelectEntityDescription(
        key="ev_charging_current_limit",
        translation_key="ev_charging_current_limit",
        icon="mdi:lightning-bolt-circle",
        options=list(CHARGING_CURRENT_OPTIONS.values()),
        entity_category=EntityCategory.CONFIG,
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
        for description in SELECT_DESCRIPTIONS:
            if description.key == "ev_charging_current_limit":
                if vehicle.ev_charging_current is None:
                    continue
            entities.append(HyundaiKiaConnectSelect(coordinator, description, vehicle))
    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectSelect(SelectEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: SelectEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self._attr_icon = description.icon

    @property
    def current_option(self) -> str | None:
        value = self.vehicle.ev_charging_current
        if value is None:
            return None
        return CHARGING_CURRENT_OPTIONS.get(value)

    async def async_select_option(self, option: str) -> None:
        level = CHARGING_CURRENT_REVERSE.get(option)
        if level is not None:
            await self.coordinator.async_set_charging_current(self.vehicle.id, level)