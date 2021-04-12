import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_HEAT
)

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, TOPIC_UPDATE, VEHICLE_ENGINE_TYPE

_LOGGER = logging.getLogger(__name__)

BINARY_INSTRUMENTS = [
    ("hood", "Hood", "vehicleStatus.hoodOpen", "mdi:car", "mdi:car", DEVICE_CLASS_DOOR),
    ("trunk", "Trunk", "vehicleStatus.trunkOpen", "mdi:car-back", "mdi:car-back", DEVICE_CLASS_DOOR),
    ("frontLeft", "Door - Front Left", "vehicleStatus.doorOpen.frontLeft", "mdi:car-door", "mdi:car-door", DEVICE_CLASS_DOOR),
    ("frontRight", "Door - Front Right", "vehicleStatus.doorOpen.frontRight", "mdi:car-door", "mdi:car-door", DEVICE_CLASS_DOOR),
    ("backLeft", "Door - Rear Left", "vehicleStatus.doorOpen.backLeft", "mdi:car-door", "mdi:car-door", DEVICE_CLASS_DOOR),
    ("backRight", "Door - Rear Right", "vehicleStatus.doorOpen.backRight", "mdi:car-door", "mdi:car-door", DEVICE_CLASS_DOOR),
    #("doorLock", "Door Lock", "vehicleStatus.doorLock", "mdi:lock", "mdi:lock-open-variant", DEVICE_CLASS_LOCK),
    ("engine", "Engine", "vehicleStatus.engine", "mdi:engine", "mdi:engine-off", DEVICE_CLASS_POWER),
    ("tirePressureLampAll", "Tire Pressure - All", "vehicleStatus.tirePressureLamp.tirePressureLampAll", "mdi:car-tire-alert", "mdi:car-tire-alert", DEVICE_CLASS_PROBLEM),
    ("tirePressureLampFL", "Tire Pressure - Front Left", "vehicleStatus.tirePressureLamp.tirePressureLampFL", "mdi:car-tire-alert", "mdi:car-tire-alert", DEVICE_CLASS_PROBLEM),
    ("tirePressureLampFR", "Tire Pressure - Front Right", "vehicleStatus.tirePressureLamp.tirePressureLampFR", "mdi:car-tire-alert", "mdi:car-tire-alert", DEVICE_CLASS_PROBLEM),
    ("tirePressureLampRL", "Tire Pressure - Rear Left", "vehicleStatus.tirePressureLamp.tirePressureLampRL", "mdi:car-tire-alert", "mdi:car-tire-alert", DEVICE_CLASS_PROBLEM),
    ("tirePressureLampRR", "Tire Pressure - Rear Right", "vehicleStatus.tirePressureLamp.tirePressureLampRR", "mdi:car-tire-alert", "mdi:car-tire-alert", DEVICE_CLASS_PROBLEM),
    ("airConditioner", "Air Conditioner", "vehicleStatus.airCtrlOn", "mdi:air-conditioner", "mdi:air-conditioner", DEVICE_CLASS_POWER),
    ("defrost", "Defroster", "vehicleStatus.defrost", "mdi:car-defrost-front", "mdi:car-defrost-front", None),
]

async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    if vehicle.engine_type is VEHICLE_ENGINE_TYPE.EV or vehicle.engine_type is VEHICLE_ENGINE_TYPE.PHEV:
        BINARY_INSTRUMENTS.append(("charging", "Charging", "vehicleStatus.evStatus.batteryCharge", None, None, DEVICE_CLASS_BATTERY_CHARGING))
        BINARY_INSTRUMENTS.append(("pluggedIn", "Plugged In", "vehicleStatus.evStatus.batteryPlugin", None, None, DEVICE_CLASS_PLUG))
    if vehicle.engine_type is VEHICLE_ENGINE_TYPE.PHEV or vehicle.engine_type is VEHICLE_ENGINE_TYPE.IC:
        BINARY_INSTRUMENTS.append(("lowFuelLight", "Low Fuel Light", "vehicleStatus.evStatus.lowFuelLight", "mdi:gas-station-off", "mdi:gas-station", None))

    binary_sensors = [
        InstrumentSensor(hass, config_entry, vehicle, id, description, key, on_icon, off_icon, device_class)
        for id, description, key, on_icon, off_icon, device_class in BINARY_INSTRUMENTS
    ]

    async_add_entities(binary_sensors, True)
    async_add_entities([VehicleEntity(hass, config_entry, vehicle)], True)

class InstrumentSensor(KiaUvoEntity):
    def __init__(
        self, hass, config_entry, vehicle: Vehicle, id, description, key, on_icon, off_icon, device_class
    ):
        super().__init__(hass, config_entry, vehicle)
        self.id = id
        self.description = description
        self.key = key
        self.on_icon = on_icon
        self.off_icon = off_icon
        self._device_class = device_class

    @property
    def icon(self):
        return self.on_icon if self.is_on else self.off_icon

    @property
    def is_on(self) -> bool:
        return bool(self.getChildValue(self.vehicle.vehicle_data, self.key))

    @property
    def state(self):
        if self._device_class == DEVICE_CLASS_LOCK:
            return "off" if self.is_on else "on"
        return "on" if self.is_on else "off"

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return f"{self.vehicle.name} {self.description}"

    @property
    def unique_id(self):
        return f"{DOMAIN}-{self.id}-{self.vehicle.id}"

class VehicleEntity(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)

    @property
    def state(self):
        return "on"

    @property
    def is_on(self) -> bool:
        return True

    @property
    def state_attributes(self):
        return {"vehicle_data": self.vehicle.vehicle_data}

    @property
    def name(self):
        return f"{self.vehicle.name} Data"

    @property
    def unique_id(self):
        return f"{DOMAIN}-all-data-{self.vehicle.id}"