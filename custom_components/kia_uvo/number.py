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
from homeassistant.exceptions import HomeAssistantError
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
        translation_key="ev_charge_limits_ac",
        icon="mdi:ev-plug-type2",
        native_min_value=50,
        native_max_value=100,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
    ),
    NumberEntityDescription(
        key=DC_CHARGING_LIMIT_KEY,
        translation_key="ev_charge_limits_dc",
        icon="mdi:ev-plug-ccs2",
        native_min_value=50,
        native_max_value=100,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
    ),
    NumberEntityDescription(
        key=V2L_LIMIT_KEY,
        translation_key="ev_v2l_discharge_limit",
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
            if description.key in (AC_CHARGING_LIMIT_KEY, DC_CHARGING_LIMIT_KEY):
                if getattr(vehicle, description.key, None) is not None:
                    entities.append(
                        HyundaiKiaConnectNumber(coordinator, description, vehicle)
                    )
            elif getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectNumber(coordinator, description, vehicle)
                )

    async_add_entities(entities)
    return True


PARALLEL_UPDATES = 1


class HyundaiKiaConnectNumber(NumberEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: NumberEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._key = description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = description.icon
        self._attr_mode = NumberMode.SLIDER
        self._attr_device_class = description.device_class

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return getattr(self.vehicle, self._key)

    @staticmethod
    def _is_valid_charge_limit(val) -> bool:
        """Check if a charge limit value is a valid integer 50-100 in steps of 10."""
        return isinstance(val, (int, float)) and int(val) in range(50, 101, 10)

    async def async_set_native_value(self, value: float) -> None:
        """Set new charging limit."""
        if (
            self.entity_description.key == AC_CHARGING_LIMIT_KEY
            and self.vehicle.ev_charge_limits_ac == int(value)
        ):
            return
        if (
            self.entity_description.key == DC_CHARGING_LIMIT_KEY
            and self.vehicle.ev_charge_limits_dc == int(value)
        ):
            return

        # set new limits
        if self.entity_description.key == AC_CHARGING_LIMIT_KEY:
            ac = int(value)
            dc = self.vehicle.ev_charge_limits_dc
            if not self._is_valid_charge_limit(dc):
                _LOGGER.error(
                    "Cannot set charge limit: the DC charging limit is not "
                    "available yet (%r). Try performing a force refresh first, "
                    "or set the DC slider to a valid value (50-100%%).",
                    dc,
                )
                raise HomeAssistantError(
                    "Cannot set charge limit: the DC charging limit "
                    "is not available yet. Try performing a force refresh "
                    "first, or set the DC slider to a valid value (50-100%)."
                )
            await self.coordinator.async_set_charge_limits(self.vehicle.id, ac, int(dc))
        elif self.entity_description.key == DC_CHARGING_LIMIT_KEY:
            ac = self.vehicle.ev_charge_limits_ac
            dc = int(value)
            if not self._is_valid_charge_limit(ac):
                _LOGGER.error(
                    "Cannot set charge limit: the AC charging limit is not "
                    "available yet (%r). Try performing a force refresh first, "
                    "or set the AC slider to a valid value (50-100%%).",
                    ac,
                )
                raise HomeAssistantError(
                    "Cannot set charge limit: the AC charging limit "
                    "is not available yet. Try performing a force refresh "
                    "first, or set the AC slider to a valid value (50-100%)."
                )
            await self.coordinator.async_set_charge_limits(self.vehicle.id, int(ac), dc)
        elif self.entity_description.key == V2L_LIMIT_KEY:
            v2l = value
            await self.coordinator.async_set_v2l_limit(self.vehicle.id, v2l)

        self.async_write_ha_state()

    @property
    def native_min_value(self):
        """Return native_min_value as reported in by the sensor"""
        return self.entity_description.native_min_value

    @property
    def native_max_value(self):
        """Returnnative_max_value as reported in by the sensor"""
        return self.entity_description.native_max_value

    @property
    def native_step(self):
        """Return step value as reported in by the sensor"""
        return self.entity_description.native_step

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value was reported in by the sensor"""
        if self.entity_description.native_unit_of_measurement == DYNAMIC_UNIT:
            return getattr(self.vehicle, self._key + "_unit")
        else:
            return self.entity_description.native_unit_of_measurement
