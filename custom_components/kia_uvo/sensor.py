"""Sensor for Hyundai / Kia Connect integration."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Final

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    TIME_MINUTES,
    ENERGY_WATT_HOUR,
    ENERGY_KILO_WATT_HOUR,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DYNAMIC_UNIT
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key="_total_driving_range",
        name="Total Driving Range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="_odometer",
        name="Odometer",
        icon="mdi:speedometer",
        native_unit_of_measurement=DYNAMIC_UNIT,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="_last_service_distance",
        name="Last Service",
        icon="mdi:car-wrench",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="_next_service_distance",
        name="Next Service",
        icon="mdi:car-wrench",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="car_battery_percentage",
        name="Car Battery Level",
        icon="mdi:car-battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="last_updated_at",
        name="Last Updated At",
        icon="mdi:update",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="ev_battery_percentage",
        name="EV Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    SensorEntityDescription(
        key="_ev_driving_range",
        name="EV Range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="_fuel_driving_range",
        name="Fuel Driving Range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="fuel_level",
        name="Fuel Level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fuel",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="_air_temperature",
        name="Set Temperature",
        native_unit_of_measurement=DYNAMIC_UNIT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="ev_estimated_current_charge_duration",
        name="Estimated Charge Duration",
        icon="mdi:ev-station",
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key="ev_estimated_fast_charge_duration",
        name="Estimated Fast Charge Duration",
        icon="mdi:ev-station",
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key="ev_estimated_portable_charge_duration",
        name="Estimated portable Charge Duration",
        icon="mdi:ev-station",
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key="ev_estimated_station_charge_duration",
        name="Estimated Station Charge Duration",
        icon="mdi:ev-station",
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key="_ev_target_range_charge_AC",
        name="Target Range of Charge AC",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="_ev_target_range_charge_DC",
        name="Target Range of Charge DC",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="total_power_consumed",
        name="Monthly Energy Consumption",
        icon="mdi:car-electric",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Need to remove km hard coding.  Underlying API needs this fixed first.  EU always does KM.
    SensorEntityDescription(
        key="power_consumption_30d",
        name="Average Energy Consumption",
        icon="mdi:car-electric",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{ENERGY_WATT_HOUR}/km",
    ),
    SensorEntityDescription(
        key="front_left_seat_status",
        name="Front Left Seat",
        icon="mdi:car-seat-heater",
    ),
    SensorEntityDescription(
        key="front_right_seat_status",
        name="Front Right Seat",
        icon="mdi:car-seat-heater",
    ),
    SensorEntityDescription(
        key="rear_left_seat_status",
        name="Rear Left Seat",
        icon="mdi:car-seat-heater",
    ),
    SensorEntityDescription(
        key="rear_right_seat_status",
        name="Rear Right Seat",
        icon="mdi:car-seat-heater",
    ),
    SensorEntityDescription(
        key="_geocode_name",
        name="Geocoded Location",
        icon="mdi:map",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in SENSOR_DESCRIPTIONS:
            if getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectSensor(coordinator, description, vehicle)
                )
    async_add_entities(entities)
    return True


class HyundaiKiaConnectSensor(SensorEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect sensor class."""

    def __init__(
        self, coordinator, description: SensorEntityDescription, vehicle: Vehicle
    ):
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle)
        self._description = description
        self._key = self._description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = self._description.icon
        self._attr_name = f"{vehicle.name} {self._description.name}"
        self._attr_state_class = self._description.state_class
        self._attr_device_class = self._description.device_class

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        return getattr(self.vehicle, self._key)

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value was reported in by the sensor"""
        if self._description.native_unit_of_measurement == DYNAMIC_UNIT:
            return getattr(self.vehicle, self._key + "_unit")
        else:
            return self._description.native_unit_of_measurement

    @property
    def state_attributes(self):
        if self._description.key == "_geocode_name":
            return {"address": getattr(self.vehicle, "_geocode_address")}
