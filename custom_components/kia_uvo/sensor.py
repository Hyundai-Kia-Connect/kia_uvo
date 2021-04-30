import logging

from homeassistant.const import (
    PERCENTAGE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TIMESTAMP,
)
import homeassistant.util.dt as dt_util

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import (
    DOMAIN,
    DATA_VEHICLE_INSTANCE,
    TOPIC_UPDATE,
    NOT_APPLICABLE,
    DISTANCE_UNITS,
    VEHICLE_ENGINE_TYPE,
    UNIT_IS_DYNAMIC
)

_LOGGER = logging.getLogger(__name__)

INSTRUMENTS = [
    ("odometer", "Odometer", "odometer.value", UNIT_IS_DYNAMIC, "mdi:speedometer", None),
    ("carBattery", "Car Battery", "vehicleStatus.battery.batSoc", PERCENTAGE, "mdi:car-battery", DEVICE_CLASS_BATTERY),
    ("lastUpdated", "Last Update", "last_updated", "None", "mdi:update", DEVICE_CLASS_TIMESTAMP),
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    if vehicle.engine_type is VEHICLE_ENGINE_TYPE.EV or vehicle.engine_type is VEHICLE_ENGINE_TYPE.PHEV:
        INSTRUMENTS.append(("evBatteryPercentage", "EV Battery", "vehicleStatus.evStatus.batteryStatus", PERCENTAGE, "mdi:car-electric", DEVICE_CLASS_BATTERY))
        INSTRUMENTS.append(("evDrivingDistance", "Range by EV", "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.evModeRange.value", UNIT_IS_DYNAMIC, "mdi:road-variant", None))
        INSTRUMENTS.append(("totalDrivingDistance", "Range Total", "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.totalAvailableRange.value", UNIT_IS_DYNAMIC, "mdi:road-variant", None))
    if vehicle.engine_type is VEHICLE_ENGINE_TYPE.PHEV:
        INSTRUMENTS.append(("fuelDrivingDistance", "Range by Fuel", "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.gasModeRange.value", UNIT_IS_DYNAMIC, "mdi:road-variant", None))
    if vehicle.engine_type is VEHICLE_ENGINE_TYPE.IC:
        INSTRUMENTS.append(("fuelDrivingDistance", "Range by Fuel", "vehicleStatus.dte.value", UNIT_IS_DYNAMIC, "mdi:road-variant", None))

    sensors = [
        InstrumentSensor(
            hass, config_entry, vehicle, id, description, key, unit, icon, device_class
        )
        for id, description, key, unit, icon, device_class in INSTRUMENTS
    ]

    async_add_entities(sensors, True)

class InstrumentSensor(KiaUvoEntity):
    def __init__(
        self,
        hass,
        config_entry,
        vehicle: Vehicle,
        id,
        description,
        key,
        unit,
        icon,
        device_class,
    ):
        super().__init__(hass, config_entry, vehicle)
        self._id = id
        self._description = description
        self._key = key
        self._unit = unit
        self._icon = icon
        self._device_class = device_class

    @property
    def state(self):
        if self._id == "lastUpdated":
            return dt_util.as_local(self.vehicle.last_updated)

        value = self.getChildValue(self.vehicle.vehicle_data, self._key)

        if value is None:
            value = NOT_APPLICABLE

        return value

    @property
    def unit_of_measurement(self):
        if self._unit == UNIT_IS_DYNAMIC:
            key_unit = self._key.replace(".value", ".unit")
            found_unit = self.getChildValue(self.vehicle.vehicle_data, key_unit)
            if found_unit in DISTANCE_UNITS:
                self._unit = DISTANCE_UNITS[found_unit]
            else:
                self._unit = NOT_APPLICABLE

        return self._unit

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return f"{self.vehicle.name} {self._description}"

    @property
    def unique_id(self):
        return f"{DOMAIN}-{self._id}-{self.vehicle.id}"
