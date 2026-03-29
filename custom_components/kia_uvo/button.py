"""Buttons for Hyundai / Kia Connect integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle in coordinator.vehicle_manager.vehicles.values():
        if (
            coordinator.vehicle_manager.region == 8
            and vehicle.engine_type != ENGINE_TYPES.EV
        ):
            entities.append(HyundaiKiaStartEngineButton(coordinator, vehicle))
    async_add_entities(entities)


class HyundaiKiaStartEngineButton(ButtonEntity, HyundaiKiaConnectEntity):
    """Expose BR remote engine start explicitly as a button."""

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_start_engine"
        self._attr_name = f"{vehicle.name} Start Engine"
        self._attr_icon = "mdi:engine"

    async def async_press(self) -> None:
        await self.coordinator.async_start_engine(self.vehicle.id)
