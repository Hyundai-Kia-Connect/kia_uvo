"""Cover for Hyundai / Kia Connect integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import Vehicle, WindowRequestOptions
from hyundai_kia_connect_api.const import WINDOW_STATE

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaCoverDescription(CoverEntityDescription):
    window_position: str


COVER_DESCRIPTIONS: Final[tuple[HyundaiKiaCoverDescription, ...]] = (
    HyundaiKiaCoverDescription(
        key="front_left_window_is_open",
        translation_key="front_left_window",
        icon="mdi:car-door",
        window_position="front_left",
    ),
    HyundaiKiaCoverDescription(
        key="front_right_window_is_open",
        translation_key="front_right_window",
        icon="mdi:car-door",
        window_position="front_right",
    ),
    HyundaiKiaCoverDescription(
        key="back_left_window_is_open",
        translation_key="back_left_window",
        icon="mdi:car-door",
        window_position="back_left",
    ),
    HyundaiKiaCoverDescription(
        key="back_right_window_is_open",
        translation_key="back_right_window",
        icon="mdi:car-door",
        window_position="back_right",
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
        for description in COVER_DESCRIPTIONS:
            if getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectCover(coordinator, description, vehicle)
                )

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectCover(CoverEntity, HyundaiKiaConnectEntity):
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaCoverDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"

    @property
    def is_closed(self) -> bool | None:
        is_open = getattr(self.vehicle, self.entity_description.key, None)
        if is_open is None:
            return None
        return not is_open

    @property
    def current_cover_position(self) -> int | None:
        is_open = getattr(self.vehicle, self.entity_description.key, None)
        if is_open is None:
            return None
        if is_open:
            return 100
        return 0

    async def async_open_cover(self, **kwargs) -> None:
        options = WindowRequestOptions(
            **{self.entity_description.window_position: WINDOW_STATE.OPEN}
        )
        await self.coordinator.async_set_windows(self.vehicle.id, options)

    async def async_close_cover(self, **kwargs) -> None:
        options = WindowRequestOptions(
            **{self.entity_description.window_position: WINDOW_STATE.CLOSED}
        )
        await self.coordinator.async_set_windows(self.vehicle.id, options)

    async def async_stop_cover(self, **kwargs) -> None:
        options = WindowRequestOptions(
            **{self.entity_description.window_position: WINDOW_STATE.CLOSED}
        )
        await self.coordinator.async_set_windows(self.vehicle.id, options)

    async def async_set_cover_position(self, position: int, **kwargs) -> None:
        if position == 0:
            state = WINDOW_STATE.CLOSED
        elif position <= 49:
            state = WINDOW_STATE.VENTILATION
        else:
            state = WINDOW_STATE.OPEN
        options = WindowRequestOptions(
            **{self.entity_description.window_position: state}
        )
        await self.coordinator.async_set_windows(self.vehicle.id, options)
