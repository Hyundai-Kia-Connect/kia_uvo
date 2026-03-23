"""Switch for Hyundai / Kia Connect integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

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
    on_action: str
    off_action: str


SWITCH_DESCRIPTIONS: Final[tuple[HyundaiKiaSwitchDescription, ...]] = (
    HyundaiKiaSwitchDescription(
        key="ev_battery_is_charging",
        name="EV Charging",
        icon="mdi:ev-station",
        on_action="async_start_charge",
        off_action="async_stop_charge",
    ),
    HyundaiKiaSwitchDescription(
        key="air_control_is_on",
        name="Climate",
        icon="mdi:air-conditioner",
        on_action="async_start_climate_default",
        off_action="async_stop_climate",
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
            if description.key == "ev_battery_is_charging":
                if getattr(vehicle, "ev_battery_percentage", None) is not None:
                    entities.append(
                        HyundaiKiaConnectSwitch(coordinator, description, vehicle)
                    )
            elif getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectSwitch(coordinator, description, vehicle)
                )

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class HyundaiKiaConnectSwitch(SwitchEntity, HyundaiKiaConnectEntity):
    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaSwitchDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._description = description
        self._key = description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{self._key}"
        self._attr_icon = description.icon
        self._attr_name = f"{vehicle.name} {description.name}"

    @property
    def is_on(self) -> bool | None:
        return getattr(self.vehicle, self._key, None)

    async def async_turn_on(self, **kwargs) -> None:
        await getattr(self.coordinator, self._description.on_action)(self.vehicle.id)

    async def async_turn_off(self, **kwargs) -> None:
        await getattr(self.coordinator, self._description.off_action)(self.vehicle.id)
