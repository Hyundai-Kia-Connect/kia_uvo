"""Button for Hyundai / Kia Connect integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import Vehicle

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaButtonDescription(ButtonEntityDescription):
    press_action: str
    exists_fn: Callable[[Vehicle], bool] = lambda _: True
    enabled_fn: Callable[[Vehicle], bool] = lambda _: True


BUTTON_DESCRIPTIONS: Final[tuple[HyundaiKiaButtonDescription, ...]] = (
    HyundaiKiaButtonDescription(
        key="force_refresh",
        translation_key="force_refresh",
        icon="mdi:refresh",
        press_action="async_force_refresh_vehicle",
    ),
    HyundaiKiaButtonDescription(
        key="start_hazard_lights",
        translation_key="start_hazard_lights",
        icon="mdi:hazard-lights",
        press_action="async_start_hazard_lights",
        enabled_fn=lambda _: False,
    ),
    HyundaiKiaButtonDescription(
        key="start_hazard_lights_and_horn",
        translation_key="start_hazard_lights_and_horn",
        icon="mdi:car-emergency",
        press_action="async_start_hazard_lights_and_horn",
        enabled_fn=lambda _: False,
    ),
    HyundaiKiaButtonDescription(
        key="start_valet_mode",
        translation_key="start_valet_mode",
        icon="mdi:key-variant",
        press_action="async_start_valet_mode",
        exists_fn=lambda vehicle: vehicle.supports_valet_mode,
    ),
    HyundaiKiaButtonDescription(
        key="stop_valet_mode",
        translation_key="stop_valet_mode",
        icon="mdi:key-variant",
        press_action="async_stop_valet_mode",
        exists_fn=lambda vehicle: vehicle.supports_valet_mode,
    ),
    HyundaiKiaButtonDescription(
        key="open_all_windows",
        translation_key="open_all_windows",
        icon="mdi:window-maximize",
        press_action="async_open_all_windows",
        exists_fn=lambda vehicle: (
            vehicle.supports_window_control
            and vehicle.front_left_window_is_open is not None
        ),
    ),
    HyundaiKiaButtonDescription(
        key="close_all_windows",
        translation_key="close_all_windows",
        icon="mdi:window-minimize",
        press_action="async_close_all_windows",
        exists_fn=lambda vehicle: (
            vehicle.supports_window_control
            and vehicle.front_left_window_is_open is not None
        ),
    ),
    HyundaiKiaButtonDescription(
        key="vent_all_windows",
        translation_key="vent_all_windows",
        icon="mdi:window-open-variant",
        press_action="async_vent_all_windows",
        exists_fn=lambda vehicle: (
            vehicle.supports_window_control
            and vehicle.front_left_window_is_open is not None
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
        for description in BUTTON_DESCRIPTIONS:
            if description.exists_fn(vehicle):
                entities.append(
                    HyundaiKiaConnectButton(coordinator, description, vehicle)
                )

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectButton(ButtonEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaButtonDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._key = description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = description.icon
        self._attr_entity_registry_enabled_default = description.enabled_fn(vehicle)

    async def async_press(self) -> None:
        await getattr(self.coordinator, self.entity_description.press_action)(
            self.vehicle.id
        )
