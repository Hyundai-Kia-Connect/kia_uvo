"""Select entities for Hyundai / Kia Connect integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from hyundai_kia_connect_api import Vehicle

from .const import CLIMATE_DURATION_OPTIONS, DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaSelectDescription(SelectEntityDescription):
    """Describes a Hyundai / Kia Connect select entity."""

    value_fn: Callable[[HyundaiKiaConnectDataUpdateCoordinator, str], str | None]
    exists_fn: Callable[[Vehicle], bool]
    set_fn: Callable[[HyundaiKiaConnectDataUpdateCoordinator, str, str], None]


SELECT_DESCRIPTIONS: Final[tuple[HyundaiKiaSelectDescription, ...]] = (
    HyundaiKiaSelectDescription(
        key="climate_duration",
        translation_key="climate_duration",
        icon="mdi:timer",
        options=list(CLIMATE_DURATION_OPTIONS),
        value_fn=lambda coordinator, vid: coordinator.get_climate_duration_option(vid),
        exists_fn=lambda vehicle: vehicle.supports.climate_duration_setting is True,
        set_fn=lambda coordinator, vid, option: coordinator.set_climate_duration_option(
            vid, option
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
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
    """Vehicle feature option the user controls directly."""

    entity_description: HyundaiKiaSelectDescription

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaSelectDescription,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the select entity."""
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        return self.entity_description.value_fn(self.coordinator, self.vehicle.id)

    async def async_select_option(self, option: str) -> None:
        """Store the new option locally; nothing is sent to the car."""
        self.entity_description.set_fn(self.coordinator, self.vehicle.id, option)
        self.async_write_ha_state()
