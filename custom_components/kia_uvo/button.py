from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Final

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaButtonEntityDescription(ButtonEntityDescription):
    """Describe Hyundai / Kia Connect button entities."""

    service: str
    payload: dict[str, Any] | None = None
    capability: Callable[[Vehicle], bool] | None = None


BUTTONS: Final[tuple[HyundaiKiaButtonEntityDescription, ...]] = (
    HyundaiKiaButtonEntityDescription(
        key="update_cached",
        name="Update (cached)",
        icon="mdi:update",
        service="update",
    ),
    HyundaiKiaButtonEntityDescription(
        key="force_update",
        name="Force update",
        icon="mdi:cloud-refresh",
        service="force_update",
    ),
    HyundaiKiaButtonEntityDescription(
        key="lock",
        name="Lock",
        icon="mdi:lock",
        service="lock",
    ),
    HyundaiKiaButtonEntityDescription(
        key="unlock",
        name="Unlock",
        icon="mdi:lock-open",
        service="unlock",
    ),
    HyundaiKiaButtonEntityDescription(
        key="start_climate",
        name="Start climate",
        icon="mdi:car-seat-heater",
        service="start_climate",
    ),
    HyundaiKiaButtonEntityDescription(
        key="stop_climate",
        name="Stop climate",
        icon="mdi:car-seat-cooler",
        service="stop_climate",
    ),
    HyundaiKiaButtonEntityDescription(
        key="start_charge",
        name="Start charge",
        icon="mdi:ev-station",
        service="start_charge",
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
    HyundaiKiaButtonEntityDescription(
        key="stop_charge",
        name="Stop charge",
        icon="mdi:power-plug-off",
        service="stop_charge",
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
    HyundaiKiaButtonEntityDescription(
        key="open_charge_port",
        name="Open charge port",
        icon="mdi:ev-plug-type2",
        service="open_charge_port",
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
    HyundaiKiaButtonEntityDescription(
        key="close_charge_port",
        name="Close charge port",
        icon="mdi:ev-plug-ccs2",
        service="close_charge_port",
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
    HyundaiKiaButtonEntityDescription(
        key="set_charge_limits_80",
        name="Set AC/DC limit to 80%",
        icon="mdi:battery-80",
        service="set_charge_limits",
        payload={"ac_limit": 80, "dc_limit": 80},
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
    HyundaiKiaButtonEntityDescription(
        key="set_charge_limits_100",
        name="Set AC/DC limit to 100%",
        icon="mdi:battery",
        service="set_charge_limits",
        payload={"ac_limit": 100, "dc_limit": 100},
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
    HyundaiKiaButtonEntityDescription(
        key="set_charging_current_100",
        name="Charging current 100%",
        icon="mdi:current-ac",
        service="set_charging_current",
        payload={"level": 100},
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
    HyundaiKiaButtonEntityDescription(
        key="set_charging_current_60",
        name="Charging current 60%",
        icon="mdi:current-ac",
        service="set_charging_current",
        payload={"level": 60},
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HyundaiKiaConnectButton] = []
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in BUTTONS:
            if description.capability is None or description.capability(vehicle):
                entities.append(
                    HyundaiKiaConnectButton(
                        coordinator=coordinator,
                        description=description,
                        vehicle=vehicle,
                    )
                )
    async_add_entities(entities)


class HyundaiKiaConnectButton(ButtonEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect button entity."""

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaButtonEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self._attr_name = f"{vehicle.name} {description.name}"
        self._attr_icon = description.icon
        if description.entity_category:
            self._attr_entity_category = description.entity_category

    async def async_press(self) -> None:
        payload = dict(self.entity_description.payload or {})
        device_id = self.registry_entry.device_id

        await self.hass.services.async_call(
            DOMAIN,
            self.entity_description.service,
            payload,
            blocking=True,
            target={"device_id": [device_id]},
        )

        await self.coordinator.async_request_refresh()
