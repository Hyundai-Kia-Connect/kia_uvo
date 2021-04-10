import logging

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle:Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    sensor_configs = [
        ("odometer", "Odometer", vehicle.vehicle_data["odometer"]["value"], "km", "mdi:speedometer", None),
        ("evBatteryPercentage", "EV Battery", vehicle.vehicle_data["vehicleStatus"]["evStatus"]["batteryStatus"], "%", "mdi:battery", "battery"),
        ("evDrivingDistance", "Range by EV", vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"][0]["rangeByFuel"]["evModeRange"]["value"], "km", "mdi:road-variant", None),
        ("fuelDrivingDistance", "Range by Fuel", vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"][0]["rangeByFuel"]["gasModeRange"]["value"], "km", "mdi:road-variant", None),
        ("totalDrivingDistance", "Range Total", vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"][0]["rangeByFuel"]["totalAvailableRange"]["value"], "km", "mdi:road-variant", None),
        ("carBattery", "Car Battery", vehicle.vehicle_data["vehicleStatus"]["battery"]["batSoc"], "%", "mdi:car-battery", "battery"),
        ("lastUpdated", "Last Update", vehicle.last_updated, "%", "mdi:update", "timestamp")
    ]

    sensors = [
        InstrumentSensor(hass, config_entry, vehicle, name, description, value, unit, icon, device_class) for name, description, value, unit, icon, device_class in sensor_configs
    ]

    async_add_entities(sensors, True)

class InstrumentSensor(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle, name, description, value, unit, icon, device_class):
        super().__init__(hass, config_entry, vehicle)
        self._name = name
        self._description = description
        self._value = value
        self._unit = unit
        self._icon = icon
        self._device_class = device_class

    @property
    def state(self):
        return self._value

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
    def state_attributes(self):
        return {
            "last_updated": self._vehicle.last_updated
        }

    @property
    def name(self):
        return f'{self._vehicle._token.vehicle_name} {self._description}'

    @property
    def unique_id(self):
        return f'kia_uvo-{self._name}-{self._vehicle._token.vehicle_id}'