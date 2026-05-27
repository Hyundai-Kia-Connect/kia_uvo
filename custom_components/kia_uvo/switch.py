"""Switch for Hyundai / Kia Connect integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import Vehicle

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaSwitchDescription(SwitchEntityDescription):
    value_fn: Callable[[Vehicle], bool | None]
    exists_fn: Callable[[Vehicle], bool]
    on_fn: Callable[[HyundaiKiaConnectDataUpdateCoordinator, str], Awaitable[None]]
    off_fn: Callable[[HyundaiKiaConnectDataUpdateCoordinator, str], Awaitable[None]]


SWITCH_DESCRIPTIONS: Final[tuple[HyundaiKiaSwitchDescription, ...]] = (
    HyundaiKiaSwitchDescription(
        key="ev_battery_is_charging",
        translation_key="ev_charging",
        icon="mdi:ev-station",
        value_fn=lambda vehicle: vehicle.ev_battery_is_charging,
        exists_fn=lambda vehicle: vehicle.ev_battery_is_charging is not None,
        on_fn=lambda coordinator, vid: coordinator.async_start_charge(vid),
        off_fn=lambda coordinator, vid: coordinator.async_stop_charge(vid),
    ),
    HyundaiKiaSwitchDescription(
        key="air_control_is_on",
        translation_key="climate",
        icon="mdi:air-conditioner",
        value_fn=lambda vehicle: vehicle.air_control_is_on,
        exists_fn=lambda vehicle: vehicle.air_control_is_on is not None,
        on_fn=lambda coordinator, vid: coordinator.async_start_climate_default(vid),
        off_fn=lambda coordinator, vid: coordinator.async_stop_climate(vid),
    ),
    # Departure schedule switches
    HyundaiKiaSwitchDescription(
        key="ev_first_departure_enabled",
        translation_key="ev_first_departure_enabled",
        icon="mdi:clock-outline",
        value_fn=lambda vehicle: vehicle.ev_first_departure_enabled,
        exists_fn=lambda vehicle: vehicle.ev_first_departure_enabled is not None,
        on_fn=lambda coordinator, vid: coordinator.async_set_departure_enabled(
            vid, 1, True
        ),
        off_fn=lambda coordinator, vid: coordinator.async_set_departure_enabled(
            vid, 1, False
        ),
    ),
    HyundaiKiaSwitchDescription(
        key="ev_second_departure_enabled",
        translation_key="ev_second_departure_enabled",
        icon="mdi:clock-outline",
        value_fn=lambda vehicle: vehicle.ev_second_departure_enabled,
        exists_fn=lambda vehicle: vehicle.ev_second_departure_enabled is not None,
        on_fn=lambda coordinator, vid: coordinator.async_set_departure_enabled(
            vid, 2, True
        ),
        off_fn=lambda coordinator, vid: coordinator.async_set_departure_enabled(
            vid, 2, False
        ),
    ),
    HyundaiKiaSwitchDescription(
        key="ev_first_departure_climate_enabled",
        translation_key="ev_first_departure_climate_enabled",
        icon="mdi:car-climate",
        value_fn=lambda vehicle: vehicle.ev_first_departure_climate_enabled,
        exists_fn=lambda vehicle: (
            vehicle.ev_first_departure_climate_enabled is not None
        ),
        on_fn=lambda coordinator, vid: coordinator.async_set_departure_climate_enabled(
            vid, 1, True
        ),
        off_fn=lambda coordinator, vid: coordinator.async_set_departure_climate_enabled(
            vid, 1, False
        ),
    ),
    HyundaiKiaSwitchDescription(
        key="ev_second_departure_climate_enabled",
        translation_key="ev_second_departure_climate_enabled",
        icon="mdi:car-climate",
        value_fn=lambda vehicle: vehicle.ev_second_departure_climate_enabled,
        exists_fn=lambda vehicle: (
            vehicle.ev_second_departure_climate_enabled is not None
        ),
        on_fn=lambda coordinator, vid: coordinator.async_set_departure_climate_enabled(
            vid, 2, True
        ),
        off_fn=lambda coordinator, vid: coordinator.async_set_departure_climate_enabled(
            vid, 2, False
        ),
    ),
    HyundaiKiaSwitchDescription(
        key="ev_first_departure_climate_defrost",
        translation_key="ev_first_departure_climate_defrost",
        icon="mdi:car-defrost-rear",
        value_fn=lambda vehicle: vehicle.ev_first_departure_climate_defrost,
        exists_fn=lambda vehicle: (
            vehicle.ev_first_departure_climate_defrost is not None
        ),
        on_fn=lambda coordinator, vid: coordinator.async_set_departure_defrost(
            vid, 1, True
        ),
        off_fn=lambda coordinator, vid: coordinator.async_set_departure_defrost(
            vid, 1, False
        ),
    ),
    HyundaiKiaSwitchDescription(
        key="ev_second_departure_climate_defrost",
        translation_key="ev_second_departure_climate_defrost",
        icon="mdi:car-defrost-rear",
        value_fn=lambda vehicle: vehicle.ev_second_departure_climate_defrost,
        exists_fn=lambda vehicle: (
            vehicle.ev_second_departure_climate_defrost is not None
        ),
        on_fn=lambda coordinator, vid: coordinator.async_set_departure_defrost(
            vid, 2, True
        ),
        off_fn=lambda coordinator, vid: coordinator.async_set_departure_defrost(
            vid, 2, False
        ),
    ),
    # Charging schedule switches
    HyundaiKiaSwitchDescription(
        key="ev_schedule_charge_enabled",
        translation_key="ev_schedule_charge_enabled",
        icon="mdi:calendar-clock",
        value_fn=lambda vehicle: vehicle.ev_schedule_charge_enabled,
        exists_fn=lambda vehicle: vehicle.ev_schedule_charge_enabled is not None,
        on_fn=lambda coordinator, vid: coordinator.async_set_schedule_charge_enabled(
            vid, True
        ),
        off_fn=lambda coordinator, vid: coordinator.async_set_schedule_charge_enabled(
            vid, False
        ),
    ),
    HyundaiKiaSwitchDescription(
        key="ev_off_peak_charge_only_enabled",
        translation_key="ev_off_peak_charge_only_enabled",
        icon="mdi:clock-outline",
        value_fn=lambda vehicle: vehicle.ev_off_peak_charge_only_enabled,
        exists_fn=lambda vehicle: vehicle.ev_off_peak_charge_only_enabled is not None,
        on_fn=lambda coordinator, vid: (
            coordinator.async_set_off_peak_charge_only_enabled(vid, True)
        ),
        off_fn=lambda coordinator, vid: (
            coordinator.async_set_off_peak_charge_only_enabled(vid, False)
        ),
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
        for description in SWITCH_DESCRIPTIONS:
            if description.exists_fn(vehicle):
                entities.append(
                    HyundaiKiaConnectSwitch(coordinator, description, vehicle)
                )

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectSwitch(SwitchEntity, HyundaiKiaConnectEntity):
    entity_description: HyundaiKiaSwitchDescription

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaSwitchDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self._attr_icon = description.icon

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.vehicle)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.on_fn(self.coordinator, self.vehicle.id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.off_fn(self.coordinator, self.vehicle.id)
