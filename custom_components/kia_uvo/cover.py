"""Cover for Hyundai / Kia Connect integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.cover import CoverEntity, CoverEntityDescription, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import EntityCategory

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.ApiImpl import WindowRequestOptions
from hyundai_kia_connect_api.const import WINDOW_STATE

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaCoverDescription(CoverEntityDescription):
    window_state_attr: str


COVER_DESCRIPTIONS: Final[tuple[HyundaiKiaCoverDescription, ...]] = (
    HyundaiKiaCoverDescription(
        key="front_left_window",
        translation_key="front_left_window",
        icon="mdi:car-door",
        window_state_attr="front_left_window_is_open",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaCoverDescription(
        key="front_right_window",
        translation_key="front_right_window",
        icon="mdi:car-door",
        window_state_attr="front_right_window_is_open",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaCoverDescription(
        key="back_left_window",
        translation_key="back_left_window",
        icon="mdi:car-door",
        window_state_attr="back_left_window_is_open",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HyundaiKiaCoverDescription(
        key="back_right_window",
        translation_key="back_right_window",
        icon="mdi:car-door",
        window_state_attr="back_right_window_is_open",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# Map description key to WindowRequestOptions field name
_WINDOW_KEY_MAP = {
    "front_left_window": "front_left",
    "front_right_window": "front_right",
    "back_left_window": "back_left",
    "back_right_window": "back_right",
}


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
            if getattr(vehicle, description.window_state_attr, None) is not None:
                entities.append(HyundaiKiaConnectCover(coordinator, description, vehicle))
    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectCover(CoverEntity, HyundaiKiaConnectEntity):
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaCoverDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self._attr_icon = description.icon
        self._window_key = _WINDOW_KEY_MAP[description.key]

    @property
    def is_closed(self) -> bool | None:
        state = getattr(self.vehicle, self.entity_description.window_state_attr, None)
        if state is None:
            return None
        return not state

    @property
    def is_opening(self) -> bool | None:
        return None

    @property
    def is_closing(self) -> bool | None:
        return None

    async def async_open_cover(self, **kwargs) -> None:
        options = WindowRequestOptions()
        setattr(options, self._window_key, WINDOW_STATE.OPEN)
        await self.coordinator.async_set_windows(self.vehicle.id, options)

    async def async_close_cover(self, **kwargs) -> None:
        options = WindowRequestOptions()
        setattr(options, self._window_key, WINDOW_STATE.CLOSED)
        await self.coordinator.async_set_windows(self.vehicle.id, options)