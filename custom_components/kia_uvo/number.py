"""Number for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from typing import Final

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DYNAMIC_UNIT
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

AC_CHARGING_LIMIT_KEY = "ev_charge_limits_ac"
DC_CHARGING_LIMIT_KEY = "ev_charge_limits_dc"
V2L_LIMIT_KEY = "ev_v2l_discharge_limit"

NUMBER_DESCRIPTIONS: Final[tuple[NumberEntityDescription, ...]] = (
    NumberEntityDescription(
        key=AC_CHARGING_LIMIT_KEY,
        name="AC Charging Limit",
        icon="mdi:ev-plug-type2",
        native_min_value=50,
        native_max_value=100,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
    ),
    NumberEntityDescription(
        key=DC_CHARGING_LIMIT_KEY,
        name="DC Charging Limit",
        icon="mdi:ev-plug-ccs2",
        native_min_value=50,
        native_max_value=100,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
    ),
    NumberEntityDescription(
        key=V2L_LIMIT_KEY,
        name="V2L Limit",
        icon="mdi:fuel-cell",
        native_min_value=20,
        native_max_value=80,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
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
        for description in NUMBER_DESCRIPTIONS:
            if getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectNumber(coordinator, description, vehicle)
                )

    async_add_entities(entities)
    return True


class HyundaiKiaConnectNumber(NumberEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: NumberEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        super().__init__(coordinator, vehicle)
        self._description = description
        self._key = self._description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = self._description.icon
        self._attr_mode = NumberMode.SLIDER
        self._attr_name = f"{vehicle.name} {self._description.name}"
        self._attr_device_class = self._description.device_class

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return getattr(self.vehicle, self._key)

    async def async_set_native_value(self, value: float) -> None:
        """Set new charging limit."""
        # force refresh of state so that we can get the value for the other charging limit
        # since we have to set both limits as compound API call.
        # await self.coordinator.async_force_update_all()

        if (
            self._description.key == AC_CHARGING_LIMIT_KEY
            and self.vehicle.ev_charge_limits_ac == int(value)
        ):
            return
        if (
            self._description.key == DC_CHARGING_LIMIT_KEY
            and self.vehicle.ev_charge_limits_dc == int(value)
        ):
            return

        # set new limits
        if self._description.key == AC_CHARGING_LIMIT_KEY:
            ac = value
            dc = self.vehicle.ev_charge_limits_dc
            await self.coordinator.async_set_charge_limits(self.vehicle.id, ac, dc)
        elif self._description.key == DC_CHARGING_LIMIT_KEY:
            ac = self.vehicle.ev_charge_limits_ac
            dc = value
            await self.coordinator.async_set_charge_limits(self.vehicle.id, ac, dc)
        elif self._description.key == V2L_LIMIT_KEY:
            v2l = value
            await self.coordinator.async_set_v2l_limit(self.vehicle.id, v2l)

        self.async_write_ha_state()

    @property
    def native_min_value(self):
        """Return native_min_value as reported in by the sensor"""
        return self._description.native_min_value

    @property
    def native_max_value(self):
        """Returnnative_max_value as reported in by the sensor"""
        return self._description.native_max_value

    @property
    def native_step(self):
        """Return step value as reported in by the sensor"""
        return self._description.native_step

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value was reported in by the sensor"""
        if self._description.native_unit_of_measurement == DYNAMIC_UNIT:
            return getattr(self.vehicle, self._key + "_unit")
        else:
            return self._description.native_unit_of_measurement
