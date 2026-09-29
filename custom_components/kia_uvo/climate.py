"""Switches for Hyundai / Kia Connect integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, ClassVar, cast

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
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
    """Set up climate platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle in coordinator.vehicle_manager.vehicles.values():
        if vehicle.air_control_is_on is not None:
            entities.append(HyundaiKiaCarClimateControlSwitch(coordinator, vehicle))
    async_add_entities(entities, True)


PARALLEL_UPDATES = 1


class HyundaiKiaCarClimateControlSwitch(HyundaiKiaConnectEntity, ClimateEntity):
    """Hyundai / Kia Connect Car Climate Control."""

    vehicle: Vehicle

    # The python lib climate request is also treated as
    # internal target state that can be sent to the car
    climate_config: ClimateRequestOptions

    # TODO: if possible in Climate, add possibility to set those
    # as well. Are there maybe additional properties?
    heat_status_int_to_str: ClassVar[dict[int | None, str | None]] = {
        None: None,
        0: "Off",
        1: "Steering Wheel and Rear Window",
        2: "Rear Window",
        3: "Steering Wheel",
    }
    heat_status_str_to_int: ClassVar[dict[str | None, int | None]] = {
        v: k for [k, v] in heat_status_int_to_str.items()
    }

    def get_internal_heat_int_for_climate_request(self) -> int:
        if (
            self.vehicle.steering_wheel_heater_is_on
            and self.vehicle.back_window_heater_is_on
        ):
            return 1
        elif self.vehicle.back_window_heater_is_on:
            return 2
        elif self.vehicle.steering_wheel_heater_is_on:
            return 3
        else:
            return 0

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the Climate Control."""
        super().__init__(coordinator, vehicle)
        self.entity_description = ClimateEntityDescription(
            key="climate_control",
            translation_key="climate_control",
            icon="mdi:air-conditioner",
            unit_of_measurement=vehicle._air_temperature_unit,
        )
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_climate_control"

        # set the Climate Request to the current actual state of the car
        self.climate_config = ClimateRequestOptions(
            set_temp=self.vehicle.air_temperature,
            climate=self.vehicle.air_control_is_on,
            heating=self.get_internal_heat_int_for_climate_request(),
            defrost=self.vehicle.defrost_is_on,
        )

    @property
    def temperature_unit(self) -> str:
        """Get the Cars Climate Control Temperature Unit."""
        if self.vehicle._air_temperature_unit:
            return UnitOfTemperature(self.vehicle._air_temperature_unit)
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current in-car temperature, or None.

        The API exposes only the HVAC setpoint (`air_temperature`); the
        vehicleStatus payload carries no cabin temperature, so there is
        nothing honest to report here (issue #1871).
        """
        return None

    @property
    def target_temperature(self) -> float | None:
        """Get the desired in-car target temperature."""
        return cast(float | None, self.vehicle.air_temperature)

    @property
    def target_temperature_step(self) -> float | None:
        """Get the step size for adjusting the in-car target temperature."""
        # TODO: get from lib
        return 0.5

    @property
    def min_temp(self) -> float:
        """Get the minimum settable temperature."""
        # TODO: get the exact per-region range from the lib
        # USA/CA report Fahrenheit; the hardcoded 14-30 °C bounds made the
        # climate slider unusable (14-30 °F) for those vehicles.
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return 62
        return 14

    @property
    def max_temp(self) -> float:
        """Get the maximum settable temperature."""
        # TODO: get the exact per-region range from the lib
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return 82
        return 30

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Get the configured climate control operation mode."""

        if not self.vehicle.air_control_is_on:
            return HVACMode.OFF

        # The API exposes no cabin temperature, so heat-vs-cool is not
        # derivable; the car decides the direction itself from the setpoint.
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction | None:
        """Get what the in-car climate control is currently doing.

        Not derivable: the API has no cabin temperature to compare a
        setpoint against (issue #1871).
        """
        if not self.vehicle.air_control_is_on:
            return HVACAction.OFF
        return None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Supported in-car climate control modes."""
        return [
            HVACMode.OFF,
            # Heat-vs-cool is decided by the car, not selectable
            HVACMode.AUTO,
        ]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Supported in-car climate control features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the operation mode of the in-car climate control."""

        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_stop_climate(self.vehicle.id)
        else:
            await self.coordinator.async_start_climate(
                self.vehicle.id, self.climate_config
            )
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the desired in-car temperature. Does not turn on the AC."""
        old_temp = self.climate_config.set_temp
        self.climate_config.set_temp = kwargs.get(ATTR_TEMPERATURE)

        # activation is controlled separately, but if system is turned on
        # and temp has changed, send update to car
        if self.hvac_mode != HVACMode.OFF and old_temp != self.climate_config.set_temp:
            # Car does not accept changing the temp after starting the heating. So we have to turn off first
            await self.coordinator.async_stop_climate(self.vehicle.id)
            # Wait, because the car ignores the start_climate command if it comes too fast after stopping
            # TODO: replace with some more event driven method
            await asyncio.sleep(5)
            await self.coordinator.async_start_climate(
                self.vehicle.id, self.climate_config
            )
        self.async_write_ha_state()
