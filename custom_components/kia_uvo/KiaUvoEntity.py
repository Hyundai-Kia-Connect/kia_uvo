from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .Vehicle import Vehicle
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, TOPIC_UPDATE

class KiaUvoEntity(Entity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        self.hass = hass
        self.config_entry = config_entry
        self.vehicle = vehicle
        self.topic_update = TOPIC_UPDATE.format(vehicle.token.vehicle_id)

    async def async_added_to_hass(self):
        @callback
        def update():
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.topic_update, update)
        )

        self.update_from_latest_data()

    @property
    def available(self) -> bool:
        return not not self.vehicle

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self.vehicle.token.vehicle_id)
            },
            "name": self.vehicle.token.vehicle_name,
            "manufacturer": "Kia",
            "model": self.vehicle.token.vehicle_model,
            "sw_version": self.vehicle.token.vehicle_registration_date,
            "via_device": (DOMAIN, self.vehicle.token.vehicle_id),
        }

    @callback
    def update_from_latest_data(self):
        self.vehicle = self.hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]