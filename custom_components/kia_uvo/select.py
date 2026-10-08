"""Select entities for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from hyundai_kia_connect_api import Vehicle

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

PRESET_EVERYDAY = "Everyday"
PRESET_MON_FRI = "Mon - Fri"
PRESET_SAT_SUN = "Sat - Sun"
PRESET_NEVER = "Never"
PRESET_CUSTOM = "Custom"

REPEAT_PRESET_OPTIONS: Final[list[str]] = [
    PRESET_EVERYDAY,
    PRESET_MON_FRI,
    PRESET_SAT_SUN,
    PRESET_NEVER,
    PRESET_CUSTOM,
]

REPEAT_PRESET_DAYS: Final[dict[str, list[int]]] = {
    PRESET_EVERYDAY: [0, 1, 2, 3, 4, 5, 6],
    PRESET_MON_FRI: [1, 2, 3, 4, 5],
    PRESET_SAT_SUN: [0, 6],
    PRESET_NEVER: [9],
}


def _days_to_preset(days: list[int] | None) -> str:
    if not days or set(days) == {9}:
        return PRESET_NEVER
    s = set(days)
    if s == {0, 1, 2, 3, 4, 5, 6}:
        return PRESET_EVERYDAY
    if s == {1, 2, 3, 4, 5}:
        return PRESET_MON_FRI
    if s == {0, 6}:
        return PRESET_SAT_SUN
    return PRESET_CUSTOM


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaSelectDescription(SelectEntityDescription):
    value_fn: Callable[[Vehicle], str | None]
    exists_fn: Callable[[Vehicle], bool]
    select_fn: Callable[
        [HyundaiKiaConnectDataUpdateCoordinator, str, str], Awaitable[None] | None
    ]


SELECT_DESCRIPTIONS: Final[tuple[HyundaiKiaSelectDescription, ...]] = (
    HyundaiKiaSelectDescription(
        key="ev_first_departure_repeat",
        translation_key="ev_first_departure_repeat",
        icon="mdi:repeat",
        options=REPEAT_PRESET_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda vehicle: _days_to_preset(vehicle.ev_first_departure_days),
        exists_fn=lambda vehicle: (
            vehicle.ev_first_departure_days is not None
            or vehicle.ev_first_departure_enabled is not None
        ),
        select_fn=lambda coordinator, vid, option: (
            coordinator.async_set_departure_days(vid, 1, REPEAT_PRESET_DAYS[option])
            if option in REPEAT_PRESET_DAYS
            else None
        ),
    ),
    HyundaiKiaSelectDescription(
        key="ev_second_departure_repeat",
        translation_key="ev_second_departure_repeat",
        icon="mdi:repeat",
        options=REPEAT_PRESET_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda vehicle: _days_to_preset(vehicle.ev_second_departure_days),
        exists_fn=lambda vehicle: (
            vehicle.ev_second_departure_days is not None
            or vehicle.ev_second_departure_enabled is not None
        ),
        select_fn=lambda coordinator, vid, option: (
            coordinator.async_set_departure_days(vid, 2, REPEAT_PRESET_DAYS[option])
            if option in REPEAT_PRESET_DAYS
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HyundaiKiaConnectSelectEntity] = []
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in SELECT_DESCRIPTIONS:
            if description.exists_fn(vehicle):
                entities.append(
                    HyundaiKiaConnectSelectEntity(coordinator, description, vehicle)
                )

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectSelectEntity(SelectEntity, HyundaiKiaConnectEntity):
    entity_description: HyundaiKiaSelectDescription

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaSelectDescription,
        vehicle: Vehicle,
    ) -> None:
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self._attr_options = list(description.options or [])

    @property
    def current_option(self) -> str | None:
        return self.entity_description.value_fn(self.vehicle)

    async def async_select_option(self, option: str) -> None:
        res = self.entity_description.select_fn(
            self.coordinator, self.vehicle.id, option
        )
        if res is not None:
            await res
