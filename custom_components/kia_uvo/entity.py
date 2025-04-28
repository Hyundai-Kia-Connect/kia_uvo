"""Base Entity for Hyundai / Kia Connect integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import BRANDS, DOMAIN, REGIONS


class HyundaiKiaConnectEntity(CoordinatorEntity):
    """Class for base entity for Hyundai / Kia Connect integration."""

    def __init__(self, coordinator, vehicle):
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.vehicle = vehicle

    @property
    def device_info(self):
        """Return device information to use for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.vehicle.id)},
            manufacturer=f"{BRANDS[self.coordinator.vehicle_manager.brand]} {REGIONS[self.coordinator.vehicle_manager.region]}",
            model=f"{self.vehicle.name} ({self.vehicle.model})",
            name=f"{self.vehicle.name} ({self.vehicle.model})",
            serial_number=f"{self.vehicle.VIN}",
        )
