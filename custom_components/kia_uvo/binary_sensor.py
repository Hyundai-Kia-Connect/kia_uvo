import logging

from homeassistant.components.binary_sensor import DEVICE_CLASS_BATTERY_CHARGING, DEVICE_CLASS_CONNECTIVITY

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)

VEHICLE_DOORS = [
    ("hood", "Hood", "mdi:car", False),
    ("trunk", "Trunk", "mdi:car-back", False),
    ("frontLeft", "Door - Front Left", "mdi:car-door", True),
    ("frontRight", "Door - Front Right", "mdi:car-door", True),
    ("backLeft", "Door - Rear Left", "mdi:car-door", True),
    ("backRight", "Door - Rear Right", "mdi:car-door", True),
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    sensors = [
        DoorSensor(hass, config_entry, vehicle, door_id, name, icon, is_normal_door)
        for door_id, name, icon, is_normal_door in VEHICLE_DOORS
    ]

    async_add_entities(sensors, True)
    async_add_entities([LockSensor(hass, config_entry, vehicle)], True)
    async_add_entities([EngineSensor(hass, config_entry, vehicle)], True)
    async_add_entities([VehicleEntity(hass, config_entry, vehicle)], True)
    if "evStatus" in vehicle.vehicle_data["vehicleStatus"]:
        async_add_entities([ChargingSensor(hass, config_entry, vehicle)], True)
        async_add_entities([PluggedInSensor(hass, config_entry, vehicle)], True)
    if "lowFuelLight" in vehicle.vehicle_data["vehicleStatus"]:
        async_add_entities([FuelLightSensor(hass, config_entry, vehicle)], True)


class DoorSensor(KiaUvoEntity):
    def __init__(
        self, hass, config_entry, vehicle: Vehicle, door_id, name, icon, is_normal_door
    ):
        super().__init__(hass, config_entry, vehicle)
        self._door_id = door_id
        self._name = name
        self._icon = icon
        self._is_normal_door = is_normal_door

    @property
    def icon(self):
        if self._is_normal_door:
            return "mdi:door-open" if self.is_on else "mdi:door-closed"
        return self._icon

    @property
    def is_on(self) -> bool:
        if self._is_normal_door:
            return (
                True
                if self.vehicle.vehicle_data["vehicleStatus"]["doorOpen"][self._door_id]
                == 1
                else False
            )
        doorName = f"{self._door_id}Open"
        return True if self.vehicle.vehicle_data["vehicleStatus"][doorName] else False

    @property
    def state(self):
        if self._is_normal_door:
            return (
                "on"
                if self.vehicle.vehicle_data["vehicleStatus"]["doorOpen"][self._door_id]
                == 1
                else "off"
            )
        doorName = f"{self._door_id}Open"
        return "on" if self.vehicle.vehicle_data["vehicleStatus"][doorName] else "off"

    @property
    def device_class(self):
        return "door"

    @property
    def name(self):
        return f"{self.vehicle.token.vehicle_name} {self._name}"

    @property
    def unique_id(self):
        return f"kia_uvo-{self._door_id}-{self.vehicle.token.vehicle_id}"


class LockSensor(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)

    @property
    def icon(self):
        return "mdi:lock" if self.is_on else "mdi:lock-open-variant"

    @property
    def is_on(self) -> bool:
        return self.vehicle.vehicle_data["vehicleStatus"]["doorLock"]

    @property
    def state(self):
        return "off" if self.vehicle.vehicle_data["vehicleStatus"]["doorLock"] else "on"

    @property
    def device_class(self):
        return "lock"

    @property
    def name(self):
        return f"{self.vehicle.token.vehicle_name} Door Lock"

    @property
    def unique_id(self):
        return f"kia_uvo-door-lock-{self.vehicle.token.vehicle_id}"


class EngineSensor(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)

    @property
    def icon(self):
        return "mdi:engine" if self.is_on else "mdi:engine-off"

    @property
    def is_on(self) -> bool:
        return self.vehicle.vehicle_data["vehicleStatus"]["engine"]

    @property
    def state(self):
        return "on" if self.vehicle.vehicle_data["vehicleStatus"]["engine"] else "off"

    @property
    def device_class(self):
        return "power"

    @property
    def name(self):
        return f"{self.vehicle.token.vehicle_name} Engine"

    @property
    def unique_id(self):
        return f"kia_uvo-engine-{self.vehicle.token.vehicle_id}"


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
        return f"{self.vehicle.token.vehicle_name} Data"

    @property
    def unique_id(self):
        return f"kia_uvo-all-data-{self.vehicle.token.vehicle_id}"


class ChargingSensor(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)

    @property
    def is_on(self) -> bool:
        return self.vehicle.vehicle_data["vehicleStatus"]["evStatus"]["batteryCharge"]

    @property
    def state(self):
        return "on" if self.vehicle.vehicle_data["vehicleStatus"]["evStatus"]["batteryCharge"] else "off"

    @property
    def device_class(self):
        return DEVICE_CLASS_BATTERY_CHARGING

    @property
    def name(self):
        return f"{self.vehicle.token.vehicle_name} Charging"

    @property
    def unique_id(self):
        return f"kia_uvo-charging-{self.vehicle.token.vehicle_id}"


class PluggedInSensor(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)

    @property
    def icon(self):
        return "mdi:power-plug" if self.is_on else "mdi:power-plug-off"

    @property
    def is_on(self) -> bool:
        return bool(self.vehicle.vehicle_data["vehicleStatus"]["evStatus"]["batteryPlugin"])

    @property
    def state(self):
        return "off" if self.vehicle.vehicle_data["vehicleStatus"]["evStatus"]["batteryPlugin"] == 0 else "on"

    @property
    def device_class(self):
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def name(self):
        return f"{self.vehicle.token.vehicle_name} Plugged In"

    @property
    def unique_id(self):
        return f"kia_uvo-plugged-in-{self.vehicle.token.vehicle_id}"


class FuelLightSensor(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)

    @property
    def icon(self):
        return "mdi:gas-station-off" if self.is_on else "mdi:gas-station"

    @property
    def is_on(self) -> bool:
        return self.vehicle.vehicle_data["vehicleStatus"]["lowFuelLight"]

    @property
    def state(self):
        return "on" if self.vehicle.vehicle_data["vehicleStatus"]["lowFuelLight"] else "off"

    @property
    def name(self):
        return f"{self.vehicle.token.vehicle_name} Fuel Light"

    @property
    def unique_id(self):
        return f"kia_uvo-fuel-light-{self.vehicle.token.vehicle_id}"
