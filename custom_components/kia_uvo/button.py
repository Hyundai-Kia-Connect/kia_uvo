"""Button for Hyundai / Kia Connect integration."""

from __future__ import annotations

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


BUTTON_DESCRIPTIONS: Final[tuple[HyundaiKiaButtonDescription, ...]] = (
    HyundaiKiaButtonDescription(
        key="force_refresh",
        translation_key="force_refresh",
        icon="mdi:refresh",
        press_action="async_force_refresh_vehicle",
    ),
    HyundaiKiaButtonDescription(
        key="open_charge_port",
        translation_key="open_charge_port",
        icon="mdi:ev-station",
        press_action="async_open_charge_port",
    ),
    HyundaiKiaButtonDescription(
        key="close_charge_port",
        translation_key="close_charge_port",
        icon="mdi:ev-station",
        press_action="async_close_charge_port",
    ),
    HyundaiKiaButtonDescription(
        key="start_hazard_lights",
        translation_key="start_hazard_lights",
        icon="mdi:car-light-alert",
        press_action="async_start_hazard_lights",
    ),
    HyundaiKiaButtonDescription(
        key="start_hazard_lights_and_horn",
        translation_key="start_hazard_lights_and_horn",
        icon="mdi:bullhorn",
        press_action="async_start_hazard_lights_and_horn",
    ),
    HyundaiKiaButtonDescription(
        key="start_valet_mode",
        translation_key="start_valet_mode",
        icon="mdi:car-key",
        press_action="async_start_valet_mode",
    ),
    HyundaiKiaButtonDescription(
        key="stop_valet_mode",
        translation_key="stop_valet_mode",
        icon="mdi:car-key",
        press_action="async_stop_valet_mode",
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
            # Charge port buttons only for vehicles with charge port
            if description.key in ("open_charge_port", "close_charge_port"):
                if vehicle.ev_charge_port_door_is_open is None:
                    continue
            entities.append(HyundaiKiaConnectButton(coordinator, description, vehicle))

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

    async def async_press(self) -> None:
        await getattr(self.coordinator, self.entity_description.press_action)(
            self.vehicle.id
        )
