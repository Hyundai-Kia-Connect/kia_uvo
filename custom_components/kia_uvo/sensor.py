import logging

from homeassistant.const import LENGTH_KILOMETERS, LENGTH_MILES

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, TOPIC_UPDATE, NOT_APPLICABLE

_LOGGER = logging.getLogger(__name__)

DISTANCE_UNITS = {1: LENGTH_KILOMETERS, 3: LENGTH_MILES}

async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle:Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    sensor_configs = [
        ("odometer",                "Odometer",         "odometer.value",                                                               "odometer.unit",   "mdi:speedometer",  None),
        ("evBatteryPercentage",     "EV Battery",       "vehicleStatus.evStatus.batteryStatus",                                         "%",    "mdi:battery",      "battery"),
        ("evDrivingDistance",       "Range by EV",      "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.evModeRange.value",           "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.evModeRange.unit",   "mdi:road-variant", None),
        ("fuelDrivingDistance",     "Range by Fuel",    "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.gasModeRange.value",          "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.gasModeRange.unit",   "mdi:road-variant", None),
        ("totalDrivingDistance",    "Range Total",      "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.totalAvailableRange.value",   "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.totalAvailableRange.unit",   "mdi:road-variant", None),
        ("carBattery",              "Car Battery",      "vehicleStatus.battery.batSoc",                                                 "%",    "mdi:car-battery",  "battery"),
        ("lastUpdated",             "Last Update",      "last_updated",                                                                 "%",    "mdi:update",       "timestamp")
    ]

    sensors = [
        InstrumentSensor(hass, config_entry, vehicle, id, description, key, unit, icon, device_class) for id, description, key, unit, icon, device_class in sensor_configs
    ]

    async_add_entities(sensors, True)

class InstrumentSensor(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle, id, description, key, unit, icon, device_class):
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
            return self.vehicle.last_updated
        
        value = self.vehicle.vehicle_data
        for x in self._key.split("."):
            try:
                value = value[x]
            except:
                try:
                    value = value[int(x)]
                except:
                    value = NOT_APPLICABLE

        return value

    @property
    def unit_of_measurement(self):
        if self._id in ("odometer", "evDrivingDistance", "fuelDrivingDistance", "totalDrivingDistance"):
            value = self.vehicle.vehicle_data
            for x in self._unit.split("."):
                try:
                    value = value[x]
                except:
                    try:
                        value = value[int(x)]
                    except:
                        value = NOT_APPLICABLE

            if value != NOT_APPLICABLE:
                unit = DISTANCE_UNITS[value]
                return unit
            else:
                return value
        else:   
            return self._unit

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return f'{self.vehicle.token.vehicle_name} {self._description}'

    @property
    def unique_id(self):
        return f'kia_uvo-{self._id}-{self.vehicle.token.vehicle_id}'