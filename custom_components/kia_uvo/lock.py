import logging

from homeassistant.components.lock import LockEntity

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, VEHICLE_LOCK_ACTION

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
    def name(self):
        return f"{self.vehicle.name} Door Lock"

    @property
    def unique_id(self):
        return f"{DOMAIN}-doorLock-{self.vehicle.id}"

    @property
    def is_locked(self):
        return self.vehicle.vehicle_data["vehicleStatus"]["doorLock"]

    @property
    def icon(self):
        return "mdi:lock" if self.is_locked else "mdi:lock-open-variant"

    async def async_lock(self):
        await self.vehicle.lock_action(VEHICLE_LOCK_ACTION.LOCK)

    async def async_unlock(self):
        await self.vehicle.lock_action(VEHICLE_LOCK_ACTION.UNLOCK)
