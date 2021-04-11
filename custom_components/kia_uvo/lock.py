import logging

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import (
    DOMAIN,
    DATA_VEHICLE_INSTANCE,
    TOPIC_UPDATE
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
    async_add_entities([Lock(hass, config_entry, vehicle)], True)

class Lock(KiaUvoEntity, LockEntity):
    def __init__(
        self,
        hass,
        config_entry,
        vehicle: Vehicle,
    ):
        super().__init__(hass, config_entry, vehicle)

    @property
    def is_locked(self):
        return self.vehicle.vehicle_data["vehicleStatus"]["doorLock"]

    async def async_lock(self):
        await self.vehicle.lock()

    async def async_unlock(self):
        await self.vehicle.unlock()