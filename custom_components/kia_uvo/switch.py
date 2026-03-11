"""Switch for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import ClimateRequestOptions, Vehicle

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

EV_CHARGING_KEY = "ev_battery_is_charging"
CLIMATE_KEY = "air_control_is_on"

SWITCH_DESCRIPTIONS: Final[tuple[SwitchEntityDescription, ...]] = (
    SwitchEntityDescription(
        key=EV_CHARGING_KEY,
        name="EV Charging",
        icon="mdi:ev-station",
    ),
    SwitchEntityDescription(
        key=CLIMATE_KEY,
        name="Climate",
        icon="mdi:air-conditioner",
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
        for description in SWITCH_DESCRIPTIONS:
            if description.key == EV_CHARGING_KEY:
                if getattr(vehicle, "ev_battery_percentage", None) is not None:
                    entities.append(
                        HyundaiKiaConnectSwitch(coordinator, description, vehicle)
                    )
            else:
                entities.append(
                    HyundaiKiaConnectSwitch(coordinator, description, vehicle)
                )

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectSwitch(SwitchEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: SwitchEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._description = description
        self._key = description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = description.icon
        self._attr_name = f"{vehicle.name} {description.name}"

    @property
    def is_on(self) -> bool | None:
        return getattr(self.vehicle, self._key, None)

    async def async_turn_on(self, **kwargs) -> None:
        if self._key == EV_CHARGING_KEY:
            await self.coordinator.async_start_charge(self.vehicle.id)
        elif self._key == CLIMATE_KEY:
            await self.coordinator.async_start_climate(
                self.vehicle.id, ClimateRequestOptions()
            )

    async def async_turn_off(self, **kwargs) -> None:
        if self._key == EV_CHARGING_KEY:
            await self.coordinator.async_stop_charge(self.vehicle.id)
        elif self._key == CLIMATE_KEY:
            await self.coordinator.async_stop_climate(self.vehicle.id)
