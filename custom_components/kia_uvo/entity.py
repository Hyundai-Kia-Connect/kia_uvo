"""Base Entity for Hyundai / Kia Connect integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from hyundai_kia_connect_api import Vehicle

from .const import BRANDS, DOMAIN, REGIONS, TRIM_NAMES
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
        identifiers = {(DOMAIN, self.vehicle.id)}
        if vin := self.vehicle.VIN:
            # Hyundai may replace its internal vehicle id after an account or
            # subscription migration. The VIN keeps HA attached to the same car.
            identifiers.add((DOMAIN, f"vin:{vin}"))
        return DeviceInfo(
            identifiers=identifiers,
            manufacturer=f"{BRANDS[self.coordinator.vehicle_manager.brand]} {REGIONS[self.coordinator.vehicle_manager.region]}",
            model=self._model_name(),
            name=self.vehicle.name,
            serial_number=f"{self.vehicle.VIN}",
        )

    def _model_name(self) -> str | None:
        """Model, plus the trim name when known and the model year."""
        model = self.vehicle.model
        if model is None:
            return None
        region = REGIONS.get(self.coordinator.vehicle_manager.region)
        trim_code = getattr(self.vehicle, "trim_code", None)
        trim = TRIM_NAMES.get(region or "", {}).get(trim_code) if trim_code else None
        if trim:
            model = f"{model} {trim}"
        if year := getattr(self.vehicle, "year", None):
            model = f"{model} ({year})"
        return str(model)
