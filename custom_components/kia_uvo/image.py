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
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        if await coordinator.async_supports_svm(vehicle_id):
            vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
            # Best-effort: populate the cache so the image entity is available
            # immediately after restart instead of waiting for a manual capture.
            # get_svm_details is a cheap cached GET — it does not wake the car.
            try:
                await coordinator.async_get_svm_details(vehicle_id)
            except Exception:
                _LOGGER.debug(
                    "SVM initial fetch failed for %s", vehicle_id, exc_info=True
                )
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
        details = coordinator.get_cached_svm_details(vehicle.id)
        self._attr_image_last_updated = details.captured_at if details else None

    def _handle_coordinator_update(self) -> None:
        """Refresh the capture timestamp when the coordinator pushes an update."""
        details = self.coordinator.get_cached_svm_details(self.vehicle.id)
        self._attr_image_last_updated = details.captured_at if details else None
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if a cached image is available."""
        return self.coordinator.get_cached_svm_details(self.vehicle.id) is not None

    async def async_image(self) -> bytes | None:
        """Return bytes of the latest SVM image."""
        details = self.coordinator.get_cached_svm_details(self.vehicle.id)
        return details.image_bytes if details else None
