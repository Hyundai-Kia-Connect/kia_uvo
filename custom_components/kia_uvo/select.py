"""Select platform for Hyundai / Kia Connect integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaSelectDescription(SelectEntityDescription):
    """Describes Hyundai/Kia select entity."""

    options_map: dict[str, int] | None = None


SELECT_DESCRIPTIONS: tuple[HyundaiKiaSelectDescription, ...] = (
    HyundaiKiaSelectDescription(
        key="ev_charging_current",
        translation_key="ev_charging_current_limit",
        icon="mdi:ev-station",
        entity_category=EntityCategory.CONFIG,
        options_map={"100%": 100, "90%": 90, "60%": 60},
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle in coordinator.vehicle_manager.vehicles.values():
        for description in SELECT_DESCRIPTIONS:
            if getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectSelect(coordinator, description, vehicle)
                )
    async_add_entities(entities, True)


class HyundaiKiaConnectSelect(SelectEntity, HyundaiKiaConnectEntity):
    """Select entity for Hyundai / Kia Connect."""

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaSelectDescription,
        vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        if description.options_map:
            self._attr_options = list(description.options_map.keys())

    @property
    def current_option(self) -> str | None:
        value = getattr(self.vehicle, self.entity_description.key, None)
        if value is None:
            return None
        if self.entity_description.options_map:
            for label, int_value in self.entity_description.options_map.items():
                if int_value == value:
                    return label
        return None

    async def async_select_option(self, option: str) -> None:
        if self.entity_description.options_map:
            value = self.entity_description.options_map.get(option)
            if value is not None:
                await self.coordinator.async_set_charging_current(
                    self.vehicle.id, value
                )
