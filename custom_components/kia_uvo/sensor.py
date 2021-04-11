import logging

from homeassistant.const import PERCENTAGE

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import (
    DOMAIN,
    DATA_VEHICLE_INSTANCE,
    TOPIC_UPDATE,
    NOT_APPLICABLE,
    DISTANCE_UNITS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    sensor_configs = [
        (
            "odometer", 
            "Odometer", 
            {"odometer.value"},
            None,
            "mdi:speedometer",
            None
        ),
        (
            "evBatteryPercentage",
            "EV Battery",
            {"vehicleStatus.evStatus.batteryStatus"},
            PERCENTAGE,
            "mdi:battery",
            "battery"
        ),
        (
            "evDrivingDistance",
            "Range by EV",
            {"vehicleStatus.evStatus.drvDistance.0.rangeByFuel.evModeRange.value"},
            None,
            "mdi:road-variant",
            None
        ),
        (
            "fuelDrivingDistance",
            "Range by Fuel",
            {"vehicleStatus.dte.value","vehicleStatus.evStatus.drvDistance.0.rangeByFuel.gasModeRange.value"},
            None,
            "mdi:road-variant",
            None
        ),
        (
            "totalDrivingDistance",
            "Range Total",
            {"vehicleStatus.evStatus.drvDistance.0.rangeByFuel.totalAvailableRange.value"},
            None,
            "mdi:road-variant",
            None
        ),
        (
            "carBattery",
            "Car Battery",
            {"vehicleStatus.battery.batSoc"},
            PERCENTAGE,
            "mdi:car-battery",
            "battery"
        ),
        (
            "lastUpdated", 
            "Last Update", 
            {"last_updated"}, 
            None, 
            "mdi:update", 
            "timestamp"
        )
    ]

    sensors = [
        InstrumentSensor(
            hass, config_entry, vehicle, id, description, key, unit, icon, device_class
        )
        for id, description, key, unit, icon, device_class in sensor_configs
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

        for key in self._key:
            _LOGGER.debug(f"{DOMAIN} - Check key for dynamic unit generation {key} {key.endswith('.value')}")
            if self._unit is None and key.endswith(".value"):
                key_unit = key.replace(".value", ".unit")
                found_unit = self.getChildValue(self.vehicle.vehicle_data, key_unit)
                if found_unit in DISTANCE_UNITS:
                    self._unit = DISTANCE_UNITS[found_unit]
                    break

    def getChildValue(self, value, key):
        for x in key.split("."):
            try:
                value = value[x]
            except:
                try:
                    value = value[int(x)]
                except:
                    value = NOT_APPLICABLE
        return value

    @property
    def state(self):
        if self._id == "lastUpdated":
            return self.vehicle.last_updated

        value = self.vehicle.vehicle_data

        for key in self._key:
            value = self.getChildValue(value, key)
            if value != NOT_APPLICABLE:
                break

        return value

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return f"{self.vehicle.token.vehicle_name} {self._description}"

    @property
    def unique_id(self):
        return f"kia_uvo-{self._id}-{self.vehicle.token.vehicle_id}"
