"""Switch for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
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
    HyundaiKiaSwitchDescription(
        key="ev_charge_port_door_is_open",
        translation_key="ev_charge_port_door",
        icon="mdi:ev-plug-charging",
        value_fn=lambda vehicle: vehicle.ev_charge_port_door_is_open,
        exists_fn=lambda vehicle: vehicle.ev_charge_port_door_is_open is not None,
        on_fn=lambda coordinator, vid: coordinator.async_open_charge_port(vid),
        off_fn=lambda coordinator, vid: coordinator.async_close_charge_port(vid),
    ),
    HyundaiKiaSwitchDescription(
        key="valet_mode_control",
        translation_key="valet_mode_control",
        icon="mdi:key-variant",
        value_fn=lambda vehicle: vehicle.valet_mode_active,
        exists_fn=lambda vehicle: (
            vehicle.supports_valet_mode and vehicle.valet_mode_active is not None
        ),
        on_fn=lambda coordinator, vid: coordinator.async_start_valet_mode(vid),
        off_fn=lambda coordinator, vid: coordinator.async_stop_valet_mode(vid),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[SwitchEntity] = []
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in SWITCH_DESCRIPTIONS:
            if description.exists_fn(vehicle):
                entities.append(
                    HyundaiKiaConnectSwitch(coordinator, description, vehicle)
                )
        if vehicle.supports_svm:
            entities.append(SVMDewarpSwitch(coordinator, vehicle))

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


class SVMDewarpSwitch(SwitchEntity, HyundaiKiaConnectEntity, RestoreEntity):
    """Toggle fisheye dewarp on this vehicle's SVM camera views.

    Presentation preference, not a vehicle command, so it does not use the
    SWITCH_DESCRIPTIONS table (whose value_fn/exists_fn take only the Vehicle).
    State lives on the coordinator so the SVM image entities read it at render
    time; RestoreEntity re-applies it after a restart.
    """

    _attr_icon = "mdi:panorama-variant-outline"
    _attr_translation_key = "svm_dewarp"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the SVM dewarp toggle."""
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_svm_dewarp"

    @property
    def is_on(self) -> bool:
        """Return True if dewarp is enabled for this vehicle."""
        return self.coordinator.svm_dewarp_enabled(self.vehicle.id)

    async def async_added_to_hass(self) -> None:
        """Restore the dewarp preference after a restart."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        self.coordinator.set_svm_dewarp(
            self.vehicle.id, state is not None and state.state == STATE_ON
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable dewarp."""
        self.coordinator.set_svm_dewarp(self.vehicle.id, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable dewarp."""
        self.coordinator.set_svm_dewarp(self.vehicle.id, False)
        self.async_write_ha_state()
