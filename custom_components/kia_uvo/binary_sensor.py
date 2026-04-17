"""Sensor for Hyundai / Kia Connect integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.const import EntityCategory
from hyundai_kia_connect_api import Vehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class HyundaiKiaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes custom binary sensor entities."""

    is_on: Callable[[Vehicle], bool] | None = None
    on_icon: str | None = None
    off_icon: str | None = None


SENSOR_DESCRIPTIONS: Final[tuple[HyundaiKiaBinarySensorEntityDescription, ...]] = (
    HyundaiKiaBinarySensorEntityDescription(
        key="engine_is_running",
        translation_key="engine_is_running",
        is_on=lambda vehicle: vehicle.engine_is_running,
        on_icon="mdi:engine",
        off_icon="mdi:engine-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="defrost_is_on",
        translation_key="defrost_is_on",
        is_on=lambda vehicle: vehicle.defrost_is_on,
        on_icon="mdi:car-defrost-front",
        off_icon="mdi:car-defrost-front",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="steering_wheel_heater_is_on",
        translation_key="steering_wheel_heater_is_on",
        is_on=lambda vehicle: vehicle.steering_wheel_heater_is_on,
        on_icon="mdi:steering",
        off_icon="mdi:steering",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_window_heater_is_on",
        translation_key="back_window_heater_is_on",
        is_on=lambda vehicle: vehicle.back_window_heater_is_on,
        on_icon="mdi:car-defrost-rear",
        off_icon="mdi:car-defrost-rear",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="side_mirror_heater_is_on",
        translation_key="side_mirror_heater_is_on",
        is_on=lambda vehicle: vehicle.side_mirror_heater_is_on,
        on_icon="mdi:car-side",
        off_icon="mdi:car-side",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_left_door_is_open",
        translation_key="front_left_door_is_open",
        is_on=lambda vehicle: vehicle.front_left_door_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_right_door_is_open",
        translation_key="front_right_door_is_open",
        is_on=lambda vehicle: vehicle.front_right_door_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_left_door_is_open",
        translation_key="back_left_door_is_open",
        is_on=lambda vehicle: vehicle.back_left_door_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_right_door_is_open",
        translation_key="back_right_door_is_open",
        is_on=lambda vehicle: vehicle.back_right_door_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="trunk_is_open",
        translation_key="trunk_is_open",
        is_on=lambda vehicle: vehicle.trunk_is_open,
        on_icon="mdi:car-back",
        off_icon="mdi:car-back",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="hood_is_open",
        translation_key="hood_is_open",
        is_on=lambda vehicle: vehicle.hood_is_open,
        on_icon="mdi:car",
        off_icon="mdi:car",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_left_window_is_open",
        translation_key="front_left_window_is_open",
        is_on=lambda vehicle: vehicle.front_left_window_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_right_window_is_open",
        translation_key="front_right_window_is_open",
        is_on=lambda vehicle: vehicle.front_right_window_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_left_window_is_open",
        translation_key="back_left_window_is_open",
        is_on=lambda vehicle: vehicle.back_left_window_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_right_window_is_open",
        translation_key="back_right_window_is_open",
        is_on=lambda vehicle: vehicle.back_right_window_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ev_battery_is_charging",
        translation_key="ev_battery_is_charging",
        is_on=lambda vehicle: vehicle.ev_battery_is_charging,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ev_battery_is_plugged_in",
        translation_key="ev_battery_is_plugged_in",
        is_on=lambda vehicle: vehicle.ev_battery_is_plugged_in,
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="fuel_level_is_low",
        translation_key="fuel_level_is_low",
        is_on=lambda vehicle: vehicle.fuel_level_is_low,
        on_icon="mdi:gas-station-off",
        off_icon="mdi:gas-station",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="smart_key_battery_warning_is_on",
        translation_key="smart_key_battery_warning_is_on",
        is_on=lambda vehicle: vehicle.smart_key_battery_warning_is_on,
        on_icon="mdi:battery-alert",
        off_icon="mdi:battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="washer_fluid_warning_is_on",
        translation_key="washer_fluid_warning_is_on",
        is_on=lambda vehicle: vehicle.washer_fluid_warning_is_on,
        on_icon="mdi:wiper-wash-alert",
        off_icon="mdi:wiper-wash",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="tire_pressure_all_warning_is_on",
        translation_key="tire_pressure_all_warning_is_on",
        is_on=lambda vehicle: vehicle.tire_pressure_all_warning_is_on,
        on_icon="mdi:car-tire-alert",
        off_icon="mdi:car-tire-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="tire_pressure_rear_left_warning_is_on",
        translation_key="tire_pressure_rear_left_warning_is_on",
        is_on=lambda vehicle: vehicle.tire_pressure_rear_left_warning_is_on,
        on_icon="mdi:car-tire-alert",
        off_icon="mdi:car-tire-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="tire_pressure_front_left_warning_is_on",
        translation_key="tire_pressure_front_left_warning_is_on",
        is_on=lambda vehicle: vehicle.tire_pressure_front_left_warning_is_on,
        on_icon="mdi:car-tire-alert",
        off_icon="mdi:car-tire-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="tire_pressure_front_right_warning_is_on",
        translation_key="tire_pressure_front_right_warning_is_on",
        is_on=lambda vehicle: vehicle.tire_pressure_front_right_warning_is_on,
        on_icon="mdi:car-tire-alert",
        off_icon="mdi:car-tire-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="tire_pressure_rear_right_warning_is_on",
        translation_key="tire_pressure_rear_right_warning_is_on",
        is_on=lambda vehicle: vehicle.tire_pressure_rear_right_warning_is_on,
        on_icon="mdi:car-tire-alert",
        off_icon="mdi:car-tire-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="air_control_is_on",
        translation_key="air_control_is_on",
        is_on=lambda vehicle: vehicle.air_control_is_on,
        on_icon="mdi:air-conditioner",
        off_icon="mdi:air-conditioner",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ev_charge_port_door_is_open",
        translation_key="ev_charge_port_door_is_open",
        is_on=lambda vehicle: vehicle.ev_charge_port_door_is_open,
        on_icon="mdi:ev-station",
        off_icon="mdi:ev-station",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ev_first_departure_enabled",
        translation_key="ev_first_departure_enabled",
        is_on=lambda vehicle: vehicle.ev_first_departure_enabled,
        on_icon="mdi:clock-outline",
        off_icon="mdi:clock-outline",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ev_second_departure_enabled",
        translation_key="ev_second_departure_enabled",
        is_on=lambda vehicle: vehicle.ev_second_departure_enabled,
        on_icon="mdi:clock-outline",
        off_icon="mdi:clock-outline",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="brake_fluid_warning_is_on",
        translation_key="brake_fluid_warning_is_on",
        is_on=lambda vehicle: vehicle.brake_fluid_warning_is_on,
        on_icon="mdi:car-brake-alert",
        off_icon="mdi:car-brake-fluid-level",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="sunroof_is_open",
        translation_key="sunroof_is_open",
        is_on=lambda vehicle: vehicle.sunroof_is_open,
        on_icon="mdi:window-closed",
        off_icon="mdi:window-closed",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="accessory_on",
        translation_key="accessory_on",
        is_on=lambda vehicle: vehicle.accessory_on,
        on_icon="mdi:car-key",
        off_icon="mdi:car-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ign3",
        translation_key="ign3",
        is_on=lambda vehicle: vehicle.ign3,
        on_icon="mdi:key",
        off_icon="mdi:car-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="remote_ignition",
        translation_key="remote_ignition",
        is_on=lambda vehicle: vehicle.remote_ignition,
        on_icon="mdi:remote",
        off_icon="mdi:remote-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="transmission_condition",
        translation_key="transmission_condition",
        is_on=lambda vehicle: vehicle.transmission_condition,
        on_icon="mdi:car-shift-pattern",
        off_icon="mdi:car",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="sleep_mode_check",
        translation_key="sleep_mode_check",
        is_on=lambda vehicle: vehicle.sleep_mode_check,
        on_icon="mdi:sleep",
        off_icon="mdi:sleep-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="headlamp_status",
        translation_key="headlamp_status",
        is_on=lambda vehicle: vehicle.headlamp_status,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="headlamp_left_low",
        translation_key="headlamp_left_low",
        is_on=lambda vehicle: vehicle.headlamp_left_low,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="headlamp_right_low",
        translation_key="headlamp_right_low",
        is_on=lambda vehicle: vehicle.headlamp_right_low,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="stop_lamp_left",
        translation_key="stop_lamp_left",
        is_on=lambda vehicle: vehicle.stop_lamp_left,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="stop_lamp_right",
        translation_key="stop_lamp_right",
        is_on=lambda vehicle: vehicle.stop_lamp_right,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="turn_signal_left_front",
        translation_key="turn_signal_left_front",
        is_on=lambda vehicle: vehicle.turn_signal_left_front,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="turn_signal_right_front",
        translation_key="turn_signal_right_front",
        is_on=lambda vehicle: vehicle.turn_signal_right_front,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="turn_signal_left_rear",
        translation_key="turn_signal_left_rear",
        is_on=lambda vehicle: vehicle.turn_signal_left_rear,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="turn_signal_right_rear",
        translation_key="turn_signal_right_rear",
        is_on=lambda vehicle: vehicle.turn_signal_right_rear,
        on_icon="mdi:lightbulb-alert-outline",
        off_icon="mdi:lightbulb-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="is_locked",
        translation_key="is_locked",
        is_on=lambda vehicle: not vehicle.is_locked,
        device_class=BinarySensorDeviceClass.LOCK,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Seat heater sensors derived from seat status strings
    HyundaiKiaBinarySensorEntityDescription(
        key="front_left_seat_heater_on",
        translation_key="front_left_seat_heater_on",
        is_on=lambda vehicle: vehicle.front_left_seat_status,
        on_icon="mdi:seat-heater",
        off_icon="mdi:seat-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_right_seat_heater_on",
        translation_key="front_right_seat_heater_on",
        is_on=lambda vehicle: vehicle.front_right_seat_status,
        on_icon="mdi:seat-heater",
        off_icon="mdi:seat-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="rear_left_seat_heater_on",
        translation_key="rear_left_seat_heater_on",
        is_on=lambda vehicle: vehicle.rear_left_seat_status,
        on_icon="mdi:seat-heater",
        off_icon="mdi:seat-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="rear_right_seat_heater_on",
        translation_key="rear_right_seat_heater_on",
        is_on=lambda vehicle: vehicle.rear_right_seat_status,
        on_icon="mdi:seat-heater",
        off_icon="mdi:seat-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HyundaiKiaConnectBinarySensor] = []
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in SENSOR_DESCRIPTIONS:
            if getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectBinarySensor(coordinator, description, vehicle)
                )
    async_add_entities(entities)
    return True


PARALLEL_UPDATES = 0


class HyundaiKiaConnectBinarySensor(BinarySensorEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect binary sensor class."""

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaBinarySensorEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description: HyundaiKiaBinarySensorEntityDescription = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        if description.entity_category:
            self._attr_entity_category = description.entity_category

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.entity_description.is_on is not None:
            return self.entity_description.is_on(self.vehicle)
        return None

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if (
            self.entity_description.on_icon == self.entity_description.off_icon
        ) is None:
            return BinarySensorEntity.icon
        return (
            self.entity_description.on_icon
            if self.is_on
            else self.entity_description.off_icon
        )