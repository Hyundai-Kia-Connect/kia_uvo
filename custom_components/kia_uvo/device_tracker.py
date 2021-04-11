import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
    async_add_entities([LocationTracker(hass, config_entry, vehicle)], True)


class LocationTracker(KiaUvoEntity, TrackerEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)

    @property
    def latitude(self):
        return self.vehicle.vehicle_data["vehicleLocation"]["coord"]["lat"]

    @property
    def longitude(self):
        return self.vehicle.vehicle_data["vehicleLocation"]["coord"]["lon"]

    @property
    def icon(self):
        return "mdi:map-marker-outline"

    @property
    def source_type(self):
        return SOURCE_TYPE_GPS

    @property
    def name(self):
        return f"{self.vehicle.token.vehicle_name} Location"

    @property
    def unique_id(self):
        return f"kia_uvo-location-{self.vehicle.token.vehicle_id}"
