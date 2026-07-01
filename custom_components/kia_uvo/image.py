"""Image platform for Hyundai / Kia Connect integration."""

from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from hyundai_kia_connect_api import Vehicle

from .const import BRAND_HYUNDAI, DOMAIN, REGION_USA
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up image platform."""
    coordinator: HyundaiKiaConnectDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.unique_id
    ]

    if (
        coordinator.vehicle_manager.region != REGION_USA
        or coordinator.vehicle_manager.brand != BRAND_HYUNDAI
    ):
        return

    entities = []
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        if await coordinator.async_supports_svm(vehicle_id):
            vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
            entities.append(SVMImageEntity(coordinator, vehicle))

    async_add_entities(entities)


PARALLEL_UPDATES = 0


class SVMImageEntity(ImageEntity, HyundaiKiaConnectEntity):
    """SVM composite image entity."""

    _attr_translation_key = "svm_image"
    _attr_icon = "mdi:car-360"

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the SVM image entity."""
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_svm_image"

    @property
    def available(self) -> bool:
        """Return True if a cached image is available."""
        return self.vehicle.id in self.coordinator._svm_details

    async def async_image(self) -> bytes | None:
        """Return bytes of the latest SVM image."""
        details = self.coordinator._svm_details.get(self.vehicle.id)
        if details is None:
            details = await self.coordinator.async_get_svm_details(self.vehicle.id)
        return details.image_bytes if details else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return metadata attributes for the captured image."""
        details = self.coordinator._svm_details.get(self.vehicle.id)
        if details is None:
            return {}
        return {
            "captured_at": (
                details.captured_at.isoformat() if details.captured_at else None
            ),
            "heading": details.heading,
            "speed": (
                {"value": details.speed[0], "unit": details.speed[1]}
                if details.speed and details.speed[0] is not None
                else None
            ),
            "door_open": details.door_open,
            "trunk_open": details.trunk_open,
        }
