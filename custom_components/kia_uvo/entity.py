"""Base Entity for Hyundai / Kia Connect integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from hyundai_kia_connect_api import Vehicle

from .const import BRANDS, DOMAIN, REGIONS
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator


class HyundaiKiaConnectEntity(
    CoordinatorEntity[HyundaiKiaConnectDataUpdateCoordinator]
):
    """Class for base entity for Hyundai / Kia Connect integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.vehicle = vehicle

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information to use for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.vehicle.id)},
            manufacturer=f"{BRANDS[self.coordinator.vehicle_manager.brand]} {REGIONS[self.coordinator.vehicle_manager.region]}",
            model=self.vehicle.model,
            name=self.vehicle.name,
            serial_number=f"{self.vehicle.VIN}",
        )
