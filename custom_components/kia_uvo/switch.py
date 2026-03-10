"""Switch for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import ClimateRequestOptions, Vehicle

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
        if getattr(vehicle, "ev_battery_percentage", None) is not None:
            entities.append(EVChargingSwitch(coordinator, vehicle))
        entities.append(ClimateSwitch(coordinator, vehicle))

    async_add_entities(entities)
    return True


PARALLEL_UPDATES = 1


class EVChargingSwitch(SwitchEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ):
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_ev_charging"
        self._attr_name = f"{vehicle.name} EV Charging"
        self._attr_icon = "mdi:ev-station"

    @property
    def is_on(self) -> bool | None:
        return getattr(self.vehicle, "ev_battery_is_charging", None)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_start_charge(self.vehicle.id)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_stop_charge(self.vehicle.id)


class ClimateSwitch(SwitchEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ):
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_climate"
        self._attr_name = f"{vehicle.name} Climate"
        self._attr_icon = "mdi:air-conditioner"

    @property
    def is_on(self) -> bool | None:
        return getattr(self.vehicle, "air_control_is_on", None)

    async def async_turn_on(self, **kwargs) -> None:
        climate_options = ClimateRequestOptions()
        await self.coordinator.async_start_climate(self.vehicle.id, climate_options)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_stop_climate(self.vehicle.id)
