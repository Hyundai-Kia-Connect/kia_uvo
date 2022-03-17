"""Device Tracker for Hyundai / Kia Connect integration."""
from __future__ import annotations

import logging
from typing import Final

from hyundai_kia_connect_api import Vehicle, VehicleManager

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

CHARGING_LIMIT_DESCRIPTIONS: Final[tuple[NumberEntityDescription, ...]] = (
    NumberEntityDescription(
        key="_ac_charging_limit",
        name="AC Charging Limit",
        icon="mdi:ev-plug-type2",
        min_value=50,
        max_value=100,
        step=10,
    ),
    NumberEntityDescription(
        key="_dc_charging_limit",
        name="DC Charging Limit",
        icon="mdi:ev-plug-ccs2",
        min_value=50,
        max_value=100,
        step=10,
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
        for descr in CHARGING_LIMIT_DESCRIPTIONS:
            entities.append(HyundaiKiaChargingLimitNumber(coordinator, descr, vehicle))

    async_add_entities(entities)
    return True


class HyundaiKiaChargingLimitNumber(NumberEntity, HyundaiKiaConnectEntity):
    _vehicle_manager: VehicleManager
    _vehicle: Vehicle

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: NumberEntityDescription,
        vehicle: Vehicle,
    ):
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._vehicle_manager = coordinator.vehicle_manager
        self._vehicle = vehicle

    def set_value(self, value: float) -> None:
        """Set new charging limit."""
        if(self.entity_description.key == "_ac_charging_limit"):
            # TODO: force refresh of existing charge limits to leave
            # the other one as is - instead of believing the cached state.
            self._vehicle_manager.api.set_charge_limits(
                self._vehicle_manager.token,
                self.vehicle,
                int(value),
                dc_limit=self._vehicle.)

    async def async_set_value(self, value: float) -> None:
        """Set new charging limit."""
        await self.hass.async_add_executor_job(self.set_value, value)
