"""Sensor for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from typing import Final
from datetime import date

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
    EntityCategory,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHARGING_CURRENTS, DOMAIN, DYNAMIC_UNIT
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key="_total_driving_range",
        translation_key="total_driving_range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="_odometer",
        translation_key="odometer",
        icon="mdi:speedometer",
        native_unit_of_measurement=DYNAMIC_UNIT,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="_last_service_distance",
        translation_key="last_service_distance",
        icon="mdi:car-wrench",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="_next_service_distance",
        translation_key="next_service_distance",
        icon="mdi:car-wrench",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="car_battery_percentage",
        translation_key="car_battery_percentage",
        icon="mdi:car-battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="last_updated_at",
        translation_key="last_updated_at",
        icon="mdi:update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="ev_battery_percentage",
        translation_key="ev_battery_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ev_battery_soh_percentage",
        translation_key="ev_battery_soh_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ev_battery_remain",
        translation_key="ev_battery_remain",
        native_unit_of_measurement=UnitOfEnergy.KILO_JOULE,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ev_battery_capacity",
        translation_key="ev_battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_JOULE,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="_ev_driving_range",
        translation_key="ev_driving_range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="_fuel_driving_range",
        translation_key="fuel_driving_range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fuel",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="_air_temperature",
        translation_key="air_temperature",
        native_unit_of_measurement=DYNAMIC_UNIT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="ev_estimated_current_charge_duration",
        translation_key="ev_estimated_current_charge_duration",
        icon="mdi:ev-station",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="ev_estimated_fast_charge_duration",
        translation_key="ev_estimated_fast_charge_duration",
        icon="mdi:ev-station",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="ev_estimated_portable_charge_duration",
        translation_key="ev_estimated_portable_charge_duration",
        icon="mdi:ev-station",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="ev_estimated_station_charge_duration",
        translation_key="ev_estimated_station_charge_duration",
        icon="mdi:ev-station",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="_ev_target_range_charge_AC",
        translation_key="ev_target_range_charge_ac",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="_ev_target_range_charge_DC",
        translation_key="ev_target_range_charge_dc",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    SensorEntityDescription(
        key="total_power_consumed",
        translation_key="total_power_consumed",
        icon="mdi:car-electric",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="total_power_regenerated",
        translation_key="total_power_regenerated",
        icon="mdi:car-electric",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    # Need to remove km hard coding.  Underlying API needs this fixed first.  EU always does KM.
    SensorEntityDescription(
        key="power_consumption_30d",
        translation_key="power_consumption_30d",
        icon="mdi:car-electric",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{UnitOfEnergy.WATT_HOUR}/km",
    ),
    SensorEntityDescription(
        key="front_left_seat_status",
        translation_key="front_left_seat_status",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="front_right_seat_status",
        translation_key="front_right_seat_status",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="rear_left_seat_status",
        translation_key="rear_left_seat_status",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="rear_right_seat_status",
        translation_key="rear_right_seat_status",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="_geocode_name",
        translation_key="geocode_name",
        icon="mdi:map",
    ),
    SensorEntityDescription(
        key="dtc_count",
        translation_key="dtc_count",
        icon="mdi:alert-circle",
    ),
    SensorEntityDescription(
        key="ev_first_departure_time",
        translation_key="ev_first_departure_time",
        icon="mdi:clock-outline",
    ),
    SensorEntityDescription(
        key="ev_second_departure_time",
        translation_key="ev_second_departure_time",
        icon="mdi:clock-outline",
    ),
    SensorEntityDescription(
        key="ev_off_peak_start_time",
        translation_key="ev_off_peak_start_time",
        icon="mdi:clock-outline",
    ),
    SensorEntityDescription(
        key="ev_off_peak_end_time",
        translation_key="ev_off_peak_end_time",
        icon="mdi:clock-outline",
    ),
    SensorEntityDescription(
        key="ev_charging_current",
        translation_key="ev_charging_current",
        icon="mdi:lightning-bolt-circle",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
    ),
    SensorEntityDescription(
        key="ev_charging_power",
        translation_key="ev_charging_power",
        icon="mdi:flash",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="VIN",
        translation_key="vehicle_identification_number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
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
        if vehicle.daily_stats:
            entities.append(
                DailyDrivingStatsEntity(
                    coordinator, coordinator.vehicle_manager.vehicles[vehicle_id]
                )
            )
            entities.append(
                TodaysDailyDrivingStatsEntity(
                    coordinator, coordinator.vehicle_manager.vehicles[vehicle_id]
                )
            )
        entities.append(
            VehicleEntity(coordinator, coordinator.vehicle_manager.vehicles[vehicle_id])
        )
    async_add_entities(entities)
    return True


PARALLEL_UPDATES = 0


class HyundaiKiaConnectSensor(SensorEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect sensor class."""

    def __init__(
        self, coordinator, description: SensorEntityDescription, vehicle: Vehicle
    ):
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._key = description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = description.icon
        self._attr_state_class = description.state_class
        self._attr_device_class = description.device_class
        if description.entity_category:
            self._attr_entity_category = description.entity_category

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        value = getattr(self.vehicle, self._key)
        if self._key == "ev_charging_current":
            return CHARGING_CURRENTS.get(value, None)
        return value

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value was reported in by the sensor"""
        if self.entity_description.native_unit_of_measurement == DYNAMIC_UNIT:
            return getattr(self.vehicle, self._key + "_unit")
        else:
            return self.entity_description.native_unit_of_measurement

    @property
    def state_attributes(self):
        if self.entity_description.key == "_geocode_name":
            return {"address": getattr(self.vehicle, "_geocode_address")}
        elif self.entity_description.key == "dtc_count":
            return {"DTC Text": getattr(self.vehicle, "dtc_descriptions")}


class VehicleEntity(SensorEntity, HyundaiKiaConnectEntity):
    _attr_translation_key = "data"

    def __init__(self, coordinator, vehicle: Vehicle):
        super().__init__(coordinator, vehicle)

    @property
    def state(self):
        return "on"

    @property
    def is_on(self) -> bool:
        return True

    @property
    def state_attributes(self):
        return {
            "vehicle_data": self.vehicle.data,
            "vehicle_name": self.vehicle.name,
        }

    @property
    def unique_id(self):
        return f"{DOMAIN}-all-data-{self.vehicle.id}"


class DailyDrivingStatsEntity(SensorEntity, HyundaiKiaConnectEntity):
    _attr_translation_key = "daily_driving_stats"

    def __init__(self, coordinator, vehicle: Vehicle):
        super().__init__(coordinator, vehicle)

    @property
    def state(self):
        return len(self.vehicle.daily_stats)

    @property
    def state_attributes(self):
        m = {}
        for day in self.vehicle.daily_stats:
            key = day.date.strftime("%Y-%m-%d")
            value = {
                "total_consumed": day.total_consumed,
                "engine_consumption": day.engine_consumption,
                "climate_consumption": day.climate_consumption,
                "onboard_electronics_consumption": day.onboard_electronics_consumption,
                "battery_care_consumption": day.battery_care_consumption,
                "regenerated_energy": day.regenerated_energy,
                "distance": day.distance,
            }
            m[key] = value
        return m

    @property
    def unique_id(self):
        return f"{DOMAIN}-daily-driving-stats-{self.vehicle.id}"

    @property
    def unit_of_measurement(self):
        return UnitOfTime.DAYS


class TodaysDailyDrivingStatsEntity(SensorEntity, HyundaiKiaConnectEntity):
    _attr_translation_key = "todays_daily_driving_stats"

    def __init__(self, coordinator, vehicle: Vehicle):
        super().__init__(coordinator, vehicle)

    @property
    def state(self):
        today = date.today()
        todayskey = today.strftime("%Y-%m-%d")
        return todayskey

    @property
    def state_attributes(self):
        today = date.today()
        todayskey = today.strftime("%Y-%m-%d")
        m = {
            "today_date": todayskey,
            "total_consumed": 0,
            "engine_consumption": 0,
            "climate_consumption": 0,
            "onboard_electronics_consumption": 0,
            "battery_care_consumption": 0,
            "regenerated_energy": 0,
            "distance": 0,
        }
        for day in self.vehicle.daily_stats:
            key = day.date.strftime("%Y-%m-%d")
            if key == todayskey:
                todayvalue = {
                    "today_date": key,
                    "total_consumed": day.total_consumed,
                    "engine_consumption": day.engine_consumption,
                    "climate_consumption": day.climate_consumption,
                    "onboard_electronics_consumption": day.onboard_electronics_consumption,
                    "battery_care_consumption": day.battery_care_consumption,
                    "regenerated_energy": day.regenerated_energy,
                    "distance": day.distance,
                }
                m = todayvalue
                break
        return m

    @property
    def unique_id(self):
        return f"{DOMAIN}-todays-daily-driving-stats-{self.vehicle.id}"
