"""Time entities for Hyundai / Kia Connect integration."""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import Vehicle

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaTimeDescription(TimeEntityDescription):
    value_fn: Callable[[Vehicle], dt.time | None]
    exists_fn: Callable[[Vehicle], bool]
    set_fn: Callable[
        [HyundaiKiaConnectDataUpdateCoordinator, str, dt.time], Awaitable[None]
    ]


TIME_DESCRIPTIONS: Final[tuple[HyundaiKiaTimeDescription, ...]] = (
    HyundaiKiaTimeDescription(
        key="ev_off_peak_start_time",
        translation_key="ev_off_peak_start_time",
        icon="mdi:clock-time-ten",
        value_fn=lambda vehicle: vehicle.ev_off_peak_start_time,
        exists_fn=lambda vehicle: vehicle.ev_off_peak_start_time is not None,
        set_fn=lambda coordinator, vid, value: coordinator.async_set_off_peak_time(
            vid, start=value
        ),
    ),
    HyundaiKiaTimeDescription(
        key="ev_off_peak_end_time",
        translation_key="ev_off_peak_end_time",
        icon="mdi:clock-time-two",
        value_fn=lambda vehicle: vehicle.ev_off_peak_end_time,
        exists_fn=lambda vehicle: vehicle.ev_off_peak_end_time is not None,
        set_fn=lambda coordinator, vid, value: coordinator.async_set_off_peak_time(
            vid, end=value
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
        for description in TIME_DESCRIPTIONS:
            if description.exists_fn(vehicle):
                entities.append(
                    HyundaiKiaConnectTimeEntity(coordinator, description, vehicle)
                )

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectTimeEntity(TimeEntity, HyundaiKiaConnectEntity):
    entity_description: HyundaiKiaTimeDescription

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaTimeDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self._attr_icon = description.icon

    @property
    def native_value(self) -> dt.time | None:
        return self.entity_description.value_fn(self.vehicle)

    async def async_set_value(self, value: dt.time) -> None:
        await self.entity_description.set_fn(self.coordinator, self.vehicle.id, value)
        self.async_write_ha_state()
