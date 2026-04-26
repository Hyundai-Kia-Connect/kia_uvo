"""Switches for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from time import sleep

from hyundai_kia_connect_api import ClimateRequestOptions, Vehicle, VehicleManager

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
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        if vehicle.air_control_is_on is not None:
            async_add_entities([HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)])


PARALLEL_UPDATES = 1


class HyundaiKiaCarClimateControlSwitch(HyundaiKiaConnectEntity, ClimateEntity):
    """Hyundai / Kia Connect Car Climate Control."""

    vehicle_manager: VehicleManager
    vehicle: Vehicle

    # The python lib climate request is also treated as
    # internal target state that can be sent to the car
    climate_config: ClimateRequestOptions

    # TODO: if possible in Climate, add possibility to set those
    # as well. Are there maybe additional properties?
    heat_status_int_to_str: dict[int | None, str | None] = {
        None: None,
        0: "Off",
        1: "Steering Wheel and Rear Window",
        2: "Rear Window",
        3: "Steering Wheel",
    }
    heat_status_str_to_int = {v: k for [k, v] in heat_status_int_to_str.items()}

    def get_internal_heat_int_for_climate_request(self):
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
        self.vehicle_manager = coordinator.vehicle_manager
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_climate_control"

        # set the Climate Request to the current actual state of the car
        current_temp = self.vehicle.air_temperature
        if isinstance(current_temp, tuple):
            current_temp = current_temp[0] if current_temp[0] != "OFF" else None
        self.climate_config = ClimateRequestOptions(
            set_temp=current_temp,
            climate=self.vehicle.air_control_is_on,
            heating=self.get_internal_heat_int_for_climate_request(),
            defrost=self.vehicle.defrost_is_on,
        )

    @property
    def temperature_unit(self) -> str:
        """Get the Cars Climate Control Temperature Unit."""
        if self.vehicle._air_temperature_unit is not None:
            return self.vehicle._air_temperature_unit
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Get the current in-car temperature."""
        temp = self.vehicle.air_temperature
        if isinstance(temp, tuple):
            return temp[0] if temp[0] != "OFF" else None
        return temp if temp != "OFF" else None

    @property
    def target_temperature(self) -> float | None:
        """Get the desired in-car target temperature."""
        # TODO: use Coordinator data, not internal state
        return self.climate_config.set_temp

    @property
    def target_temperature_step(self) -> float | None:
        """Get the step size for adjusting the in-car target temperature."""
        # TODO: get from lib
        return 0.5

    # TODO: unknown
    @property
    def min_temp(self) -> float:
        """Get the minimum settable temperature."""
        # TODO: get from lib
        return 14

    # TODO: unknown
    @property
    def max_temp(self) -> float:
        """Get the maximum settable temperature."""
        # TODO: get from lib
        return 30

    @property
    def hvac_mode(self) -> str:
        """Get the configured climate control operation mode."""

        if not self.vehicle.air_control_is_on:
            return HVACMode.OFF

        current = self.current_temperature
        target = self.climate_config.set_temp

        # If we don't have both temperatures, fall back to AUTO
        if current is None or target is None:
            return HVACMode.AUTO

        # Cheating: there is no perfect mapping to either heat or cool,
        # as the API can only set target temp and then decides: so we
        # just derive the same by temperature change direction.
        if current > target:
            return HVACMode.COOL
        if current < target:
            return HVACMode.HEAT

        # TODO: what could be a sensible answer if target temp is reached?
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> str | None:
        # TODO: use Coordinator data, not internal state
        """
        Get what the in-car climate control is currently doing.

        Computed value based on current and desired temp and configured operation mode.
        """
        if not self.vehicle.air_control_is_on:
            return HVACAction.OFF

        current = self.current_temperature
        target = self.climate_config.set_temp

        if current is None or target is None:
            return HVACAction.IDLE

        # if temp is lower than target, it HEATs
        if current < target:
            return HVACAction.HEATING

        # if temp is higher than target, it COOLs
        if current > target:
            return HVACAction.COOLING

        # target temp reached
        if current == target:
            return HVACAction.IDLE

        # should not happen, fallback
        return HVACAction.OFF

    @property
    def hvac_modes(self) -> list[str]:
        """Supported in-car climate control modes."""
        return [
            HVACMode.OFF,
            # if only heater is activated
            HVACMode.HEAT,
            # if only AC is activated
            HVACMode.COOL,
        ]

    @property
    def supported_features(self) -> int:
        """Supported in-car climate control features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the operation mode of the in-car climate control."""

        if hvac_mode == HVACMode.OFF:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.stop_climate,
                self.vehicle.id,
            )
            self.vehicle.air_control_is_on = False
        else:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.start_climate,
                self.vehicle.id,
                self.climate_config,
            )
            self.vehicle.air_control_is_on = True
        self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set the desired in-car temperature. Does not turn on the AC."""
        old_temp = self.climate_config.set_temp
        self.climate_config.set_temp = kwargs.get(ATTR_TEMPERATURE)

        # activation is controlled separately, but if system is turned on
        # and temp has changed, send update to car
        if self.hvac_mode != HVACMode.OFF and old_temp != self.climate_config.set_temp:
            # Car does not accept changing the temp after starting the heating. So we have to turn off first
            await self.hass.async_add_executor_job(
                self.vehicle_manager.stop_climate,
                self.vehicle.id,
            )
            # Wait, because the car ignores the start_climate command if it comes too fast after stopping
            # TODO: replace with some more event driven method
            await self.hass.async_add_executor_job(sleep, 5.0)
            await self.hass.async_add_executor_job(
                self.vehicle_manager.start_climate,
                self.vehicle.id,
                self.climate_config,
            )
        self.coordinator.async_request_refresh()
        self.async_write_ha_state()
