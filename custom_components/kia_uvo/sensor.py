"""Sensor for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, cast

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES

from . import trip_stats
from .const import (
    CABIN_AIR_QUALITY_BANDS,
    CHARGING_CURRENTS,
    DOMAIN,
    DYNAMIC_UNIT,
    EXTERIOR_COLOR_NAMES,
    REGIONS,
    TRIM_NAMES,
)
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HyundaiKiaSensorEntityDescription(SensorEntityDescription):
    """A class that describes custom sensor entities."""

    exists: Callable[[Vehicle], bool] | None = None


def _is_electrified(vehicle: Vehicle) -> bool:
    """Return True for BEV and PHEV vehicles."""
    return vehicle.engine_type in (ENGINE_TYPES.EV, ENGINE_TYPES.PHEV)


SENSOR_DESCRIPTIONS: Final[tuple[HyundaiKiaSensorEntityDescription, ...]] = (
    HyundaiKiaSensorEntityDescription(
        key="_total_driving_range",
        translation_key="total_driving_range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_odometer",
        translation_key="odometer",
        icon="mdi:speedometer",
        native_unit_of_measurement=DYNAMIC_UNIT,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        # Odometer is a stable vehicle capability, but its value can be absent
        # during setup. Keep the entity so a later refresh can populate it.
        exists=lambda _: True,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_last_service_distance",
        translation_key="last_service_distance",
        icon="mdi:car-wrench",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_next_service_distance",
        translation_key="next_service_distance",
        icon="mdi:car-wrench",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="car_battery_percentage",
        translation_key="car_battery_percentage",
        icon="mdi:car-battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        # The 12V SoC is transient — None while the telematics unit
        # is asleep, after a 12V reset, or when the status payload
        # omits it. Don't gate creation on it: a None at setup (e.g.
        # a version-update reload) means the entity isn't yielded and
        # HA marks it "no longer provided", with no return until the
        # next reload. Always create; None -> HA `unknown`, the real
        # SoC arrives on the next poll. See #1803.
        exists=lambda _: True,
    ),
    HyundaiKiaSensorEntityDescription(
        key="last_updated_at",
        translation_key="last_updated_at",
        icon="mdi:update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="last_scanned_at",
        translation_key="last_scanned_at",
        icon="mdi:cloud-search",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_percentage",
        translation_key="ev_battery_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_soh_percentage",
        translation_key="ev_battery_soh_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_remain",
        translation_key="ev_battery_remain",
        native_unit_of_measurement=UnitOfEnergy.KILO_JOULE,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_capacity",
        translation_key="ev_battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_JOULE,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_ev_driving_range",
        translation_key="ev_driving_range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_fuel_driving_range",
        translation_key="fuel_driving_range",
        icon="mdi:road-variant",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fuel",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_air_temperature",
        translation_key="air_temperature",
        native_unit_of_measurement=DYNAMIC_UNIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        # The setpoint is transient — it is None while climate is off
        # (USA returns airTemp.value "OFF"), so don't gate on it. Gate
        # on climate presence (air_control_is_on, the same signal the
        # climate entity uses) to avoid creating an unusable sensor on
        # vehicles that report no climate. A None setpoint -> HA
        # `unknown`; the real setpoint arrives on the next poll.
        exists=lambda vehicle: (
            vehicle.air_control_is_on is not None
            or vehicle._air_temperature is not None
        ),
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_estimated_current_charge_duration",
        translation_key="ev_estimated_current_charge_duration",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_estimated_fast_charge_duration",
        translation_key="ev_estimated_fast_charge_duration",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_estimated_portable_charge_duration",
        translation_key="ev_estimated_portable_charge_duration",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_estimated_station_charge_duration",
        translation_key="ev_estimated_station_charge_duration",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Target charge range is transient — None at setup when the car is
    # asleep, telematics omits dte.rangeByFuel.totalAvailableRange, or
    # targetSOClist has a single entry (one of the two indices is then
    # absent). Value-gating here drops the entity permanently ("no longer
    # provided") on a version-update reload, and it only returns on a
    # manual reload while the value happens to be present. Gate on the
    # stable EV/PHEV capability instead so a later coordinator poll can
    # publish the range. None -> HA `unknown` until the next poll. See
    # #1842. The same gate applies to both sensors below.
    HyundaiKiaSensorEntityDescription(
        key="_ev_target_range_charge_AC",
        translation_key="ev_target_range_charge_ac",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        exists=lambda vehicle: (
            _is_electrified(vehicle) or vehicle._ev_target_range_charge_AC is not None
        ),
    ),
    HyundaiKiaSensorEntityDescription(
        key="_ev_target_range_charge_DC",
        translation_key="ev_target_range_charge_dc",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        exists=lambda vehicle: (
            _is_electrified(vehicle) or vehicle._ev_target_range_charge_DC is not None
        ),
    ),
    HyundaiKiaSensorEntityDescription(
        key="total_power_consumed",
        translation_key="total_power_consumed",
        icon="mdi:car-electric",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HyundaiKiaSensorEntityDescription(
        key="total_power_regenerated",
        translation_key="total_power_regenerated",
        icon="mdi:car-electric",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    # Need to remove km hard coding.  Underlying API needs this fixed first.  EU always does KM.
    HyundaiKiaSensorEntityDescription(
        key="power_consumption_30d",
        translation_key="power_consumption_30d",
        icon="mdi:car-electric",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{UnitOfEnergy.WATT_HOUR}/km",
    ),
    HyundaiKiaSensorEntityDescription(
        key="front_left_seat_status",
        translation_key="front_left_seat_status",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="front_right_seat_status",
        translation_key="front_right_seat_status",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="rear_left_seat_status",
        translation_key="rear_left_seat_status",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="rear_right_seat_status",
        translation_key="rear_right_seat_status",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_geocode_name",
        translation_key="geocode_name",
        icon="mdi:map",
        # The geocoded address is transient — it lives in memory and is None
        # right after a restart/reload until a poll with coordinates
        # succeeds. Don't gate creation on it: a None at setup means the
        # entity isn't yielded and HA marks it "no longer provided", with no
        # return until the next reload, even after location recovers
        # (kia_uvo #1844). Always create; None -> HA `unknown`.
        exists=lambda _: True,
    ),
    HyundaiKiaSensorEntityDescription(
        key="dtc_count",
        translation_key="dtc_count",
        icon="mdi:alert-circle",
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_first_departure_time",
        translation_key="ev_first_departure_time",
        icon="mdi:clock-outline",
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_second_departure_time",
        translation_key="ev_second_departure_time",
        icon="mdi:clock-outline",
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_off_peak_start_time",
        translation_key="ev_off_peak_start_time",
        icon="mdi:clock-outline",
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_off_peak_end_time",
        translation_key="ev_off_peak_end_time",
        icon="mdi:clock-outline",
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_charging_current",
        translation_key="ev_charging_current",
        icon="mdi:lightning-bolt-circle",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_charging_power",
        translation_key="ev_charging_power",
        icon="mdi:flash",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        # Charging power is transient and usually None at setup while
        # the vehicle is unplugged. Create the sensor for electrified
        # vehicles so a later coordinator poll can publish the value
        # without requiring an integration reload.
        exists=lambda vehicle: (
            _is_electrified(vehicle) or vehicle.ev_charging_power is not None
        ),
    ),
    HyundaiKiaSensorEntityDescription(
        key="VIN",
        translation_key="vehicle_identification_number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="cabin_pm25",
        translation_key="cabin_pm25",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.PM25,
        # Literal unit: UnitOfDensity is newer than the minimum supported HA.
        native_unit_of_measurement="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_outside_temperature",
        translation_key="outside_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="engine_type",
        translation_key="engine_type",
        icon="mdi:engine",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_chiller_rpm",
        translation_key="ev_battery_chiller_rpm",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="rpm",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_first_departure_days",
        translation_key="ev_first_departure_days",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_second_departure_days",
        translation_key="ev_second_departure_days",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_ev_first_departure_climate_temperature",
        translation_key="ev_first_departure_climate_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="_ev_second_departure_climate_temperature",
        translation_key="ev_second_departure_climate_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_pack_voltage",
        translation_key="ev_battery_pack_voltage",
        icon="mdi:car-battery",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_temperature_min",
        translation_key="ev_battery_temperature_min",
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_temperature_max",
        translation_key="ev_battery_temperature_max",
        icon="mdi:thermometer-high",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_battery_water_temperature",
        translation_key="ev_battery_water_temperature",
        icon="mdi:thermometer-water",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DYNAMIC_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_power_consumption_air_conditioning",
        translation_key="ev_power_consumption_air_conditioning",
        icon="mdi:air-conditioner",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_power_consumption_battery_cooling",
        translation_key="ev_power_consumption_battery_cooling",
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="ev_power_consumption_battery_heater",
        translation_key="ev_power_consumption_battery_heater",
        icon="mdi:radiator",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaSensorEntityDescription(
        key="location_last_updated_at",
        translation_key="location_last_updated_at",
        icon="mdi:map-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Transient like _air_temperature above: some backends (AU/NZ)
    # report the TPMS no-data sentinel whenever the car is parked
    # — nearly always the case at setup — so don't gate on the
    # value. The parsed unit is the capability signal: non-None
    # exactly for direct-TPMS vehicles (known PressureUnit), None
    # for indirect TPMS (PressureUnit 3, e.g. KONA — #1786) and
    # old-protocol vehicles, which never report a numeric
    # pressure. A None pressure -> HA `unknown` until a poll
    # catches the car driving. The same gate applies to all four
    # tire_pressure_* sensors below.
    HyundaiKiaSensorEntityDescription(
        key="tire_pressure_front_left",
        translation_key="tire_pressure_front_left",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        exists=lambda vehicle: (
            vehicle.tire_pressure_front_left is not None
            or vehicle.tire_pressure_unit is not None
        ),
    ),
    HyundaiKiaSensorEntityDescription(
        key="tire_pressure_front_right",
        translation_key="tire_pressure_front_right",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        exists=lambda vehicle: (
            vehicle.tire_pressure_front_right is not None
            or vehicle.tire_pressure_unit is not None
        ),
    ),
    HyundaiKiaSensorEntityDescription(
        key="tire_pressure_rear_left",
        translation_key="tire_pressure_rear_left",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        exists=lambda vehicle: (
            vehicle.tire_pressure_rear_left is not None
            or vehicle.tire_pressure_unit is not None
        ),
    ),
    HyundaiKiaSensorEntityDescription(
        key="tire_pressure_rear_right",
        translation_key="tire_pressure_rear_right",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=DYNAMIC_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        exists=lambda vehicle: (
            vehicle.tire_pressure_rear_right is not None
            or vehicle.tire_pressure_unit is not None
        ),
    ),
    HyundaiKiaSensorEntityDescription(
        key="drive_mode",
        translation_key="drive_mode",
        icon="mdi:car-cog",
    ),
)


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaTripSensorEntityDescription(SensorEntityDescription):
    """Describes a trip statistics sensor.

    value_fn gets the vehicle, today's date as yyyymmdd and the timezone the
    API reports trips in.
    """

    value_fn: Callable[[Vehicle, str, Any], StateType | datetime]


def _today(field: str) -> Callable[[Vehicle, str, Any], StateType]:
    """Today's total for field; 0 when there were no trips today."""

    def value(vehicle: Vehicle, today: str, _tz: Any) -> StateType:
        summary = trip_stats.today_summary(vehicle, today)
        return getattr(summary, field) if summary is not None else 0

    return value


def _month(
    field: str, empty: StateType = 0
) -> Callable[[Vehicle, str, Any], StateType]:
    """This month's figure for field; empty when no trips this month."""

    def value(vehicle: Vehicle, _today: str, _tz: Any) -> StateType:
        month = vehicle.month_trip_info
        if month is None or month.summary is None:
            return empty
        return cast(StateType, getattr(month.summary, field))

    return value


def _last(field: str) -> Callable[[Vehicle, str, Any], StateType]:
    """The last trip's figure for field."""

    def value(vehicle: Vehicle, _today: str, _tz: Any) -> StateType:
        trip = trip_stats.last_trip(vehicle)
        return cast(StateType, getattr(trip, field)) if trip is not None else None

    return value


TRIP_SENSOR_DESCRIPTIONS: Final[tuple[HyundaiKiaTripSensorEntityDescription, ...]] = (
    HyundaiKiaTripSensorEntityDescription(
        key="trip_today_distance",
        translation_key="trip_today_distance",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_today("distance"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="trip_today_drive_time",
        translation_key="trip_today_drive_time",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_today("drive_time"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="trip_today_count",
        translation_key="trip_today_count",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda v, today, _tz: trip_stats.today_trip_count(v, today),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="trip_month_distance",
        translation_key="trip_month_distance",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_month("distance"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="trip_month_drive_time",
        translation_key="trip_month_drive_time",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_month("drive_time"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="trip_month_idle_time",
        translation_key="trip_month_idle_time",
        icon="mdi:timer-pause-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_month("idle_time"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="trip_month_count",
        translation_key="trip_month_count",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda v, _today, _tz: trip_stats.month_trip_count(v),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="trip_month_avg_speed",
        translation_key="trip_month_avg_speed",
        icon="mdi:speedometer-medium",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_month("avg_speed", empty=None),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="trip_month_max_speed",
        translation_key="trip_month_max_speed",
        icon="mdi:speedometer",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_month("max_speed", empty=None),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_start",
        translation_key="last_trip_start",
        icon="mdi:car-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda v, _today, tz: trip_stats.last_trip_start(v, tz),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_end",
        translation_key="last_trip_end",
        icon="mdi:car-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda v, _today, tz: trip_stats.last_trip_end(v, tz),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_distance",
        translation_key="last_trip_distance",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=_last("distance"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_drive_time",
        translation_key="last_trip_drive_time",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_last("drive_time"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_idle_time",
        translation_key="last_trip_idle_time",
        icon="mdi:timer-pause-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last("idle_time"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_avg_speed",
        translation_key="last_trip_avg_speed",
        icon="mdi:speedometer-medium",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=_last("avg_speed"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_max_speed",
        translation_key="last_trip_max_speed",
        icon="mdi:speedometer",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=_last("max_speed"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_hard_braking",
        translation_key="last_trip_hard_braking",
        icon="mdi:car-brake-alert",
        value_fn=_last("hard_braking_count"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_rapid_acceleration",
        translation_key="last_trip_rapid_acceleration",
        icon="mdi:car-speed-limiter",
        value_fn=_last("rapid_acceleration_count"),
    ),
    HyundaiKiaTripSensorEntityDescription(
        key="last_trip_speeding",
        translation_key="last_trip_speeding",
        icon="mdi:speedometer-slow",
        value_fn=_last("excessive_speed_count"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[SensorEntity] = []
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in SENSOR_DESCRIPTIONS:
            if (
                description.key == "_geocode_name"
                and not coordinator.vehicle_manager.geocode_api_enable
            ):
                # Created only when the geolocation option is on: without it
                # the library never runs the geocode lookup, so the sensor
                # would sit `unknown` forever. With the option on, a None at
                # setup must not gate creation — see the `_geocode_name`
                # description above. Gated here, not in `exists`, because the
                # option is coordinator state.
                continue
            create = (
                description.exists(vehicle)
                if description.exists is not None
                else getattr(vehicle, description.key, None) is not None
            )
            if create:
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
        if vehicle_id in coordinator.trip_stats_vehicle_ids:
            entities.extend(
                HyundaiKiaTripSensor(coordinator, description, vehicle)
                for description in TRIP_SENSOR_DESCRIPTIONS
            )
        entities.append(
            VehicleEntity(coordinator, coordinator.vehicle_manager.vehicles[vehicle_id])
        )
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        if await coordinator.async_supports_svm(vehicle_id):
            entities.append(
                SVMStatusSensor(
                    coordinator, coordinator.vehicle_manager.vehicles[vehicle_id]
                )
            )
    async_add_entities(entities)


PARALLEL_UPDATES = 0


class HyundaiKiaConnectSensor(RestoreSensor, SensorEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect sensor class."""

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaSensorEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._key = description.key
        self._last_dynamic_unit: str | None = None
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = description.icon
        self._attr_state_class = description.state_class
        self._attr_device_class = description.device_class
        if description.entity_category:
            self._attr_entity_category = description.entity_category
        # For electrified vehicles (BEV/PHEV) the traction battery is the
        # device's primary battery. Drop the battery device_class from the
        # 12 V auxiliary sensor so Home Assistant's device-page battery picker
        # (which selects the first sensor with device_class=battery, ignoring
        # entity_category) shows the EV battery instead of the 12 V level.
        # HEV/ICE keep the 12 V as their battery. See issue #1749.
        if description.key == "car_battery_percentage":
            engine_type = getattr(vehicle, "engine_type", None)
            if engine_type in (ENGINE_TYPES.EV, ENGINE_TYPES.PHEV):
                self._attr_device_class = None

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        value = getattr(self.vehicle, self._key)
        if self._key == "ev_charging_current":
            return CHARGING_CURRENTS.get(value, None)
        if self._key in ("ev_first_departure_days", "ev_second_departure_days"):
            if isinstance(value, list):
                return ", ".join(str(d) for d in value)
            return cast(StateType | datetime, value)
        return cast(StateType | datetime, value)

    async def async_added_to_hass(self) -> None:
        """Restore the last known dynamic unit after a restart."""
        await super().async_added_to_hass()
        last_sensor_data = await self.async_get_last_sensor_data()
        if last_sensor_data is not None and last_sensor_data.native_unit_of_measurement:
            self._last_dynamic_unit = last_sensor_data.native_unit_of_measurement

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the reported unit, falling back to the last known unit.

        A poll whose payload omits the unit block would otherwise publish a
        unitless state for DYNAMIC_UNIT sensors while the device_class stays,
        which trips the recorder units_changed repair on every dropout
        (issue #1894).
        """
        if self.entity_description.native_unit_of_measurement == DYNAMIC_UNIT:
            unit = cast(str | None, getattr(self.vehicle, self._key + "_unit", None))
            if unit is not None:
                self._last_dynamic_unit = unit
                return unit
            return self._last_dynamic_unit
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the geocoded address or DTC descriptions, if applicable."""
        if self.entity_description.key == "_geocode_name":
            return {"address": self.vehicle._geocode_address}
        elif self.entity_description.key == "dtc_count":
            return {"DTC Text": self.vehicle.dtc_descriptions}
        elif self.entity_description.key == "cabin_pm25":
            level = self.vehicle.cabin_air_quality_level
            return {
                "level": level,
                "colour": CABIN_AIR_QUALITY_BANDS.get(level),
                "measured_at": self.vehicle.cabin_air_quality_measured_at,
            }
        elif self.entity_description.key == "VIN":
            return self._vehicle_details()
        return {}

    def _vehicle_details(self) -> dict[str, Any]:
        """Model year, trim and colours, by name where the code is known."""
        vehicle = self.vehicle
        region = REGIONS.get(self.coordinator.vehicle_manager.region)
        trim_code = getattr(vehicle, "trim_code", None)
        exterior = getattr(vehicle, "exterior_color_code", None)
        details = {
            "model_year": getattr(vehicle, "year", None),
            "trim": TRIM_NAMES.get(region or "", {}).get(trim_code, trim_code)
            if trim_code
            else None,
            "exterior_color": EXTERIOR_COLOR_NAMES.get(exterior, exterior)
            if exterior
            else None,
            "interior_color_code": getattr(vehicle, "interior_color_code", None),
        }
        return {key: value for key, value in details.items() if value is not None}


class VehicleEntity(SensorEntity, HyundaiKiaConnectEntity):
    """Sensor exposing the raw vehicle data as attributes."""

    _attr_translation_key = "data"

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the vehicle data sensor."""
        super().__init__(coordinator, vehicle)

    @property
    def native_value(self) -> StateType:
        """Return a constant state; the data lives in the attributes."""
        return "on"

    @property
    def is_on(self) -> bool:
        """Return True; this sensor is always on."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the raw vehicle data and name."""
        return {
            "vehicle_data": self.vehicle.data,
            "vehicle_name": self.vehicle.name,
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return f"{DOMAIN}-all-data-{self.vehicle.id}"


class DailyDrivingStatsEntity(SensorEntity, HyundaiKiaConnectEntity):
    """Number of days of driving stats, with each day as an attribute."""

    _attr_translation_key = "daily_driving_stats"

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the daily driving stats sensor."""
        super().__init__(coordinator, vehicle)

    @property
    def native_value(self) -> StateType:
        """Return the number of days with driving stats."""
        return len(self.vehicle.daily_stats)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the driving stats for each day, keyed by date."""
        m: dict[str, Any] = {}
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
    def unique_id(self) -> str:
        """Return the unique ID."""
        return f"{DOMAIN}-daily-driving-stats-{self.vehicle.id}"

    @property
    def native_unit_of_measurement(self) -> str:
        """Return days as the unit."""
        return UnitOfTime.DAYS


class TodaysDailyDrivingStatsEntity(SensorEntity, HyundaiKiaConnectEntity):
    """Today's driving stats, zeroed until the API reports today."""

    _attr_translation_key = "todays_daily_driving_stats"

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize today's driving stats sensor."""
        super().__init__(coordinator, vehicle)

    @property
    def native_value(self) -> StateType:
        """Return today's date."""
        today = date.today()
        todayskey = today.strftime("%Y-%m-%d")
        return todayskey

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return today's driving stats."""
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
    def unique_id(self) -> str:
        """Return the unique ID."""
        return f"{DOMAIN}-todays-daily-driving-stats-{self.vehicle.id}"


class SVMStatusSensor(SensorEntity, HyundaiKiaConnectEntity):
    """SVM capture metadata sensor (companion to the SVM image entity).

    The image entity cannot expose extra state attributes (ImageEntity
    finalizes state_attributes), so metadata is exposed here.
    """

    _attr_translation_key = "svm_status"
    _attr_icon = "mdi:camera-iris"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the SVM status sensor."""
        super().__init__(coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_svm_status"

    @property
    def available(self) -> bool:
        """Return True if cached SVM details are available."""
        return self.coordinator.get_cached_svm_details(self.vehicle.id) is not None

    @property
    def native_value(self) -> datetime | None:
        """Return the capture timestamp of the latest SVM image."""
        details = self.coordinator.get_cached_svm_details(self.vehicle.id)
        return cast(datetime | None, details.captured_at) if details else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return SVM metadata attributes."""
        details = self.coordinator.get_cached_svm_details(self.vehicle.id)
        if details is None:
            return {}
        return {
            "heading": details.heading,
            "speed": (
                {"value": details.speed[0], "unit": details.speed[1]}
                if details.speed and details.speed[0] is not None
                else None
            ),
            "door_open": details.door_open,
            "trunk_open": details.trunk_open,
        }


class HyundaiKiaTripSensor(SensorEntity, HyundaiKiaConnectEntity):
    """Trip statistics sensor (today, this month, last trip)."""

    entity_description: HyundaiKiaTripSensorEntityDescription

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaTripSensorEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the trip sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"

    @property
    def available(self) -> bool:
        """Unavailable when the last trip refresh failed, so a failed read
        is not shown as zero trips."""
        return super().available and bool(
            self.coordinator.trip_stats_ok.get(self.vehicle.id)
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the trip statistic."""
        tz = self.coordinator.trip_timezone
        today = datetime.now(tz).strftime("%Y%m%d")
        return self.entity_description.value_fn(self.vehicle, today, tz)
