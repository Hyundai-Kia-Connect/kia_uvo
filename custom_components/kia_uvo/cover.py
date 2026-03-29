"""Cover entities for Hyundai / Kia Connect integration."""

from __future__ import annotations

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import Vehicle, WindowRequestOptions, WINDOW_STATE

from .const import DOMAIN, REGION_BRAZIL, REGIONS
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HyundaiKiaWindowsCover] = []

    if REGIONS[coordinator.vehicle_manager.region] != REGION_BRAZIL:
        async_add_entities(entities)
        return

    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        if (
            vehicle.front_left_window_is_open is not None
            and vehicle.front_right_window_is_open is not None
            and vehicle.back_left_window_is_open is not None
            and vehicle.back_right_window_is_open is not None
        ):
            entities.append(HyundaiKiaWindowsCover(coordinator, vehicle))

    async_add_entities(entities)


class HyundaiKiaWindowsCover(HyundaiKiaConnectEntity, CoverEntity):
    """Expose the BR all-windows command as a Home Assistant cover."""

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        super().__init__(coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_windows"
        self._attr_name = f"{vehicle.name} Windows"

    @property
    def supported_features(self) -> int:
        return CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    @property
    def is_closed(self) -> bool | None:
        states = (
            self.vehicle.front_left_window_is_open,
            self.vehicle.front_right_window_is_open,
            self.vehicle.back_left_window_is_open,
            self.vehicle.back_right_window_is_open,
        )
        if any(state is None for state in states):
            return None
        return not any(states)

    async def async_open_cover(self, **kwargs) -> None:
        await self.coordinator.async_set_windows(
            self.vehicle.id,
            WindowRequestOptions(
                front_left=WINDOW_STATE.OPEN,
                front_right=WINDOW_STATE.OPEN,
                back_left=WINDOW_STATE.OPEN,
                back_right=WINDOW_STATE.OPEN,
            ),
        )

    async def async_close_cover(self, **kwargs) -> None:
        await self.coordinator.async_set_windows(
            self.vehicle.id,
            WindowRequestOptions(
                front_left=WINDOW_STATE.CLOSED,
                front_right=WINDOW_STATE.CLOSED,
                back_left=WINDOW_STATE.CLOSED,
                back_right=WINDOW_STATE.CLOSED,
            ),
        )
