from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Final

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ENGINE_TYPES
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaSwitchEntityDescription(SwitchEntityDescription):
    """Describe Hyundai / Kia Connect switch entities."""

    service_on: str
    service_off: str
    payload_on: dict[str, Any] | None = None
    payload_off: dict[str, Any] | None = None
    is_on: Callable[[Vehicle], bool | None] | None = None
    capability: Callable[[Vehicle], bool] | None = None


SWITCHES: Final[tuple[HyundaiKiaSwitchEntityDescription, ...]] = (
    HyundaiKiaSwitchEntityDescription(
        key="remote_climate",
        name="Remote climate",
        icon="mdi:car-climate-control",
        service_on="start_climate",
        service_off="stop_climate",
        # Keep payload empty by default; users can still call the service with extra fields.
        is_on=lambda v: getattr(v, "air_control_is_on", None),
    ),
    HyundaiKiaSwitchEntityDescription(
        key="charging",
        name="Charging",
        icon="mdi:ev-station",
        service_on="start_charge",
        service_off="stop_charge",
        is_on=lambda v: getattr(v, "ev_battery_is_charging", None),
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
    HyundaiKiaSwitchEntityDescription(
        key="charge_port_door",
        name="Charge port door",
        icon="mdi:ev-plug-type2",
        service_on="open_charge_port",
        service_off="close_charge_port",
        is_on=lambda v: getattr(v, "ev_charge_port_door_is_open", None),
        capability=lambda v: v.engine_type != ENGINE_TYPES.ICE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HyundaiKiaConnectSwitch] = []

    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in SWITCHES:
            if description.capability is not None and not description.capability(
                vehicle
            ):
                continue

            if description.is_on is not None and description.is_on(vehicle) is None:
                continue

            entities.append(
                HyundaiKiaConnectSwitch(
                    coordinator=coordinator,
                    description=description,
                    vehicle=vehicle,
                )
            )

    async_add_entities(entities)


class HyundaiKiaConnectSwitch(SwitchEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect switch entity."""

    entity_description: HyundaiKiaSwitchEntityDescription

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaSwitchEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self._attr_name = f"{vehicle.name} {description.name}"
        self._attr_icon = description.icon
        if description.entity_category:
            self._attr_entity_category = description.entity_category

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.is_on is None:
            return None
        return self.entity_description.is_on(self.vehicle)

    async def async_turn_on(self, **kwargs: Any) -> None:
        payload = dict(self.entity_description.payload_on or {})
        device_id = self.registry_entry.device_id

        await self.hass.services.async_call(
            DOMAIN,
            self.entity_description.service_on,
            payload,
            blocking=True,
            target={"device_id": [device_id]},
        )

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        payload = dict(self.entity_description.payload_off or {})
        device_id = self.registry_entry.device_id

        await self.hass.services.async_call(
            DOMAIN,
            self.entity_description.service_off,
            payload,
            blocking=True,
            target={"device_id": [device_id]},
        )

        await self.coordinator.async_request_refresh()
