import logging

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle:Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    _LOGGER.debug(f'Drv Distance 1 {vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"]}')

    _LOGGER.debug(f'Drv Distance 2 {vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"][0]}')

    _LOGGER.debug(f'Drv Distance 2 {vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"][0]}')

    sensor_configs = [
        ("odometer", "Odemeter", vehicle.vehicle_data["odometer"]["value"], "km", "mdi:speedometer"),
        ("evBatteryPercentage", "EV Battery Percentage", vehicle.vehicle_data["vehicleStatus"]["evStatus"]["batteryStatus"], "%", "mdi:battery"),
        ("evDrivingDistance", "EV Driving Distance", vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"][0]["rangeByFuel"]["evModeRange"]["value"], "km", "mdi:road-variant"),
        ("fuelDrivingDistance", "Fuel Driving Distance", vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"][0]["rangeByFuel"]["gasModeRange"]["value"], "km", "mdi:road-variant"),
        ("totalDrivingDistance", "Total Driving Distance", vehicle.vehicle_data["vehicleStatus"]["evStatus"]["drvDistance"][0]["rangeByFuel"]["totalAvailableRange"]["value"], "km", "mdi:road-variant"),
        ("carBattery", "Car Battery", vehicle.vehicle_data["vehicleStatus"]["battery"]["batSoc"], "%", "mdi:car-battery")
    ]

    sensors = [
        InstrumentSensor(hass, config_entry, vehicle, name, description, value, unit, icon) for name, description, value, unit, icon in sensor_configs
    ]

    async_add_entities(sensors, True)

class InstrumentSensor(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle, name, description, value, unit, icon):
        super().__init__(hass, config_entry, vehicle)
        self._name = name
        self._description = description
        self._value = value
        self._unit = unit
        self._icon = icon

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