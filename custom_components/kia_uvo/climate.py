"""Switches for Hyundai / Kia Connect integration."""
from __future__ import annotations

import logging

from hyundai_kia_connect_api import ClimateRequestOptions, Vehicle, VehicleManager

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
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
    """Set up binary_sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        async_add_entities([HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)])


class HyundaiKiaCarClimateControlSwitch(HyundaiKiaConnectEntity, ClimateEntity):
    """Hyundai / Kia Connect Car Climate Control."""

    vehicle_manager: VehicleManager
    vehicle: Vehicle

    # The python lib climate request is also treated as
    # internal target state that can be sent to the car
    climate_config: ClimateRequestOptions = ClimateRequestOptions

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the Climate Control."""
        super().__init__(coordinator, vehicle)
        self.entity_description = ClimateEntityDescription(
            key="climate_control",
            icon="mdi:air-conditioner",
            name="Climate Control",
            unit_of_measurement=vehicle._air_temperature_unit,
        )
        self.vehicle_manager = coordinator.vehicle_manager
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_climate_control"
        self._attr_name = f"{vehicle.name} Climate Control"

    @property
    def temperature_unit(self) -> str:
        """Get the Cars Climate Control Temperature Unit."""
        return self.vehicle._air_temperature_unit

    @property
    def current_temperature(self) -> float | None:
        """Get the current in-car temperature."""
        return self.vehicle.air_temperature

    @property
    def target_temperature(self) -> float | None:
        """Get the desired in-car target temperature."""
        # TODO: use Coordinator data, not internal state
        return self.climate_config.set_temp

    @property
    def target_temperature_high(self) -> float | None:
        """
        Get the desired in-car target temperature.

        There is no target temp window but this property is required for HVAC_MODE_HEAT_COOL
        """
        # TODO: use Coordinator data, not internal state
        return self.climate_config.set_temp

    @property
    def target_temperature_low(self) -> float | None:
        """
        Get the desired in-car target temperature.

        There is no target temp window but this property is required for HVAC_MODE_HEAT_COOL
        """
        # TODO: use Coordinator data, not internal state
        return self.climate_config.set_temp

    # TODO: unknown
    @property
    def target_temperature_step(self) -> float | None:
        """Get the step size for adjusting the in-car target temperature."""
        return None

    # TODO: unknown
    @property
    def min_temp(self) -> float:
        """Get the minimum temperature. This is a car, so the value is useless."""
        return 40

    # TODO: unknown
    @property
    def max_temp(self) -> float:
        """Get the maximum temperature. This is a car, so the value is useless."""
        return 0

    @property
    def hvac_mode(self) -> str:
        """Get the configured climate control operation mode."""

        # HVAC_MODE can be determined based on activation state of
        # AC and Heater. TODO: use Coordinator data, not internal state
        state = [self.climate_config.climate, self.climate_config.heating]

        if state == [0, 0]:
            return HVAC_MODE_FAN_ONLY
        elif state == [1, 0]:
            return HVAC_MODE_COOL
        elif state == [0, 1]:
            return HVAC_MODE_HEAT
        elif state == [1, 1]:
            return HVAC_MODE_HEAT_COOL
        else:
            return HVAC_MODE_OFF

    @property
    def hvac_action(self) -> str | None:
        # TODO: use Coordinator data, not internal state
        """
        Get what the in-car climate control is currently doing.

        Computed value based on current and desired temp and configured operation mode.
        """
        # if temp is lower than target, it HEATs
        if (
            self.vehicle.air_temperature < self.climate_config.set_temp
            and self.climate_config.heating != 0
        ):
            return CURRENT_HVAC_HEAT

        # if temp is higher than target and AC is turned on, it COOLs
        elif (
            self.vehicle.air_temperature > self.climate_config.set_temp
            and self.climate_config.climate != 0
        ):
            return CURRENT_HVAC_COOL

        # if temp is higher than target but AC turned off, it only blows the FAN
        # same for trying to heat up without heater
        elif (
            # try to cool
            self.vehicle.air_temperature > self.climate_config.set_temp
            and self.climate_config.climate == 1
            # try to heat
            or self.vehicle.air_temperature < self.climate_config.set_temp
            and self.climate_config.heating == 0
        ):
            return CURRENT_HVAC_FAN

        # target temp reached
        elif self.vehicle.air_temperature == self.climate_config.set_temp:
            return CURRENT_HVAC_IDLE

        # TODO: there is probably more cases, but for now assume off
        else:
            return CURRENT_HVAC_OFF

    @property
    def hvac_modes(self) -> list[str]:
        """Supported in-car climate control modes."""
        return [
            # TODO: how to determine from car state if AC system is turned on at all?
            HVAC_MODE_OFF,
            # if both climate and heater are activated
            HVAC_MODE_HEAT_COOL,
            # if only heater is activated
            HVAC_MODE_HEAT,
            # if only AC is activated
            HVAC_MODE_COOL,
            # if start_climate is called with both heater and AC off lol
            HVAC_MODE_FAN_ONLY,
        ]

    @property
    def supported_features(self) -> int:
        """Supported in-car climate control features."""
        # TODO: Range needed? "The device supports a ranged target temperature. Used for HVAC modes heat_cool and auto"
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_TEMPERATURE_RANGE

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the operation mode of the in-car climate control."""

        # update climate and heating activation according to HVAC MODE
        [self.climate_config.climate, self.climate_config.heating] = {
            HVAC_MODE_HEAT_COOL: [1, 1],
            HVAC_MODE_COOL: [1, 0],
            HVAC_MODE_HEAT: [0, 1],
            HVAC_MODE_FAN_ONLY: [0, 0],
            HVAC_MODE_OFF: [None, None],
        }[hvac_mode]

        # and send to car
        if hvac_mode is HVAC_MODE_OFF:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.api.stop_climate(
                    self.vehicle_manager.token, self.vehicle
                )
            )
        else:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.api.start_climate(
                    self.vehicle_manager.token, self.vehicle, self.climate_config
                )
            )

    async def async_set_temperature(self, **kwargs):
        """Set the desired in-car temperature. Does not turn on the AC."""
        old_temp = self.climate_config.set_temp
        self.climate_config.set_temp = kwargs.get(ATTR_TEMPERATURE)

        # activation is controlled separately, but if system is turned on
        # and temp has changed, send update to car
        if (
            self.hvac_mode is not HVAC_MODE_OFF
            and old_temp != self.climate_config.set_temp
        ):
            await self.hass.async_add_executor_job(
                self.vehicle_manager.api.start_climate(
                    self.vehicle_manager.token, self.vehicle, self.climate_config
                )
            )
