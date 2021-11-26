import logging

from homeassistant.core import callback
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_CONNECTIVITY,
)

from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, VEHICLE_ENGINE_TYPE, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    BINARY_INSTRUMENTS = [
        (
            "hood",
            "Hood",
            "vehicleStatus.hoodOpen",
            "mdi:car",
            "mdi:car",
            DEVICE_CLASS_DOOR,
        ),
        (
            "trunk",
            "Trunk",
            "vehicleStatus.trunkOpen",
            "mdi:car-back",
            "mdi:car-back",
            DEVICE_CLASS_DOOR,
        ),
        (
            "frontLeft",
            "Door - Front Left",
            "vehicleStatus.doorOpen.frontLeft",
            "mdi:car-door",
            "mdi:car-door",
            DEVICE_CLASS_DOOR,
        ),
        (
            "frontRight",
            "Door - Front Right",
            "vehicleStatus.doorOpen.frontRight",
            "mdi:car-door",
            "mdi:car-door",
            DEVICE_CLASS_DOOR,
        ),
        (
            "backLeft",
            "Door - Rear Left",
            "vehicleStatus.doorOpen.backLeft",
            "mdi:car-door",
            "mdi:car-door",
            DEVICE_CLASS_DOOR,
        ),
        (
            "backRight",
            "Door - Rear Right",
            "vehicleStatus.doorOpen.backRight",
            "mdi:car-door",
            "mdi:car-door",
            DEVICE_CLASS_DOOR,
        ),
        (
            "engine",
            "Engine",
            "vehicleStatus.engine",
            "mdi:engine",
            "mdi:engine-off",
            DEVICE_CLASS_POWER,
        ),
        (
            "tirePressureLampAll",
            "Tire Pressure - All",
            "vehicleStatus.tirePressureLamp.tirePressureLampAll",
            "mdi:car-tire-alert",
            "mdi:car-tire-alert",
            DEVICE_CLASS_PROBLEM,
        ),
        (
            "tirePressureLampFL",
            "Tire Pressure - Front Left",
            "vehicleStatus.tirePressureLamp.tirePressureLampFL",
            "mdi:car-tire-alert",
            "mdi:car-tire-alert",
            DEVICE_CLASS_PROBLEM,
        ),
        (
            "tirePressureLampFR",
            "Tire Pressure - Front Right",
            "vehicleStatus.tirePressureLamp.tirePressureLampFR",
            "mdi:car-tire-alert",
            "mdi:car-tire-alert",
            DEVICE_CLASS_PROBLEM,
        ),
        (
            "tirePressureLampRL",
            "Tire Pressure - Rear Left",
            "vehicleStatus.tirePressureLamp.tirePressureLampRL",
            "mdi:car-tire-alert",
            "mdi:car-tire-alert",
            DEVICE_CLASS_PROBLEM,
        ),
        (
            "tirePressureLampRR",
            "Tire Pressure - Rear Right",
            "vehicleStatus.tirePressureLamp.tirePressureLampRR",
            "mdi:car-tire-alert",
            "mdi:car-tire-alert",
            DEVICE_CLASS_PROBLEM,
        ),
        (
            "airConditioner",
            "Air Conditioner",
            "vehicleStatus.airCtrlOn",
            "mdi:air-conditioner",
            "mdi:air-conditioner",
            DEVICE_CLASS_POWER,
        ),
        (
            "defrost",
            "Defroster",
            "vehicleStatus.defrost",
            "mdi:car-defrost-front",
            "mdi:car-defrost-front",
            None,
        ),
        (
            "backWindowHeater",
            "Back Window Heater",
            "vehicleStatus.sideBackWindowHeat",
            "mdi:car-defrost-rear",
            "mdi:car-defrost-rear",
            None,
        ),
        (
            "sideMirrorHeater",
            "Side Mirror Heater",
            "vehicleStatus.sideMirrorHeat",
            "mdi:car-side",
            "mdi:car-side",
            None,
        ),
        (
            "steeringWheelHeater",
            "Steering Wheel Heater",
            "vehicleStatus.steerWheelHeat",
            "mdi:steering",
            "mdi:steering",
            None,
        ),
        (
            "frSeatHeatState",
            "Front Right Seat Heater",
            "vehicleStatus.seatHeaterVentState.frSeatHeatState",
            "mdi:car-seat-heater",
            "mdi:car-seat-heater",
            None,
        ),
        (
            "flSeatHeatState",
            "Front Left Seat Heater",
            "vehicleStatus.seatHeaterVentState.flSeatHeatState",
            "mdi:car-seat-heater",
            "mdi:car-seat-heater",
            None,
        ),
        (
            "rrSeatHeatState",
            "Rear Right Seat Heater",
            "vehicleStatus.seatHeaterVentState.rrSeatHeatState",
            "mdi:car-seat-heater",
            "mdi:car-seat-heater",
            None,
        ),
        (
            "rlSeatHeatState",
            "Rear Left Seat Heater",
            "vehicleStatus.seatHeaterVentState.rlSeatHeatState",
            "mdi:car-seat-heater",
            "mdi:car-seat-heater",
            None,
        ),
        (
            "lowFuelLight",
            "Low Fuel Light",
            "vehicleStatus.lowFuelLight",
            "mdi:gas-station-off",
            "mdi:gas-station",
            None,
        ),
    ]

    if (
        vehicle.engine_type is VEHICLE_ENGINE_TYPE.EV
        or vehicle.engine_type is VEHICLE_ENGINE_TYPE.PHEV
    ):
        BINARY_INSTRUMENTS.append(
            (
                "charging",
                "Charging",
                "vehicleStatus.evStatus.batteryCharge",
                None,
                None,
                DEVICE_CLASS_BATTERY_CHARGING,
            )
        )
        BINARY_INSTRUMENTS.append(
            (
                "pluggedIn",
                "Plugged In",
                "vehicleStatus.evStatus.batteryPlugin",
                None,
                None,
                DEVICE_CLASS_PLUG,
            )
        )

    binary_sensors = []

    for id, description, key, on_icon, off_icon, device_class in BINARY_INSTRUMENTS:
        if vehicle.get_child_value(key) != None:
            binary_sensors.append(
                InstrumentSensor(
                    hass,
                    config_entry,
                    vehicle,
                    id,
                    description,
                    key,
                    on_icon,
                    off_icon,
                    device_class,
                )
            )

    async_add_entities(binary_sensors, True)
    async_add_entities([VehicleEntity(hass, config_entry, vehicle)], True)
    async_add_entities([APIActionInProgress(hass, config_entry, vehicle)], True)


class InstrumentSensor(KiaUvoEntity):
    def __init__(
        self,
        hass,
        config_entry,
        vehicle: Vehicle,
        id,
        description,
        key,
        on_icon,
        off_icon,
        device_class,
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
        return bool(self.vehicle.get_child_value(self.key))

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
        return {
            "vehicle_data": self.vehicle.vehicle_data,
            "vehicle_name": self.vehicle.name,
        }

    @property
    def name(self):
        return f"{self.vehicle.name} Data"

    @property
    def unique_id(self):
        return f"{DOMAIN}-all-data-{self.vehicle.id}"


class APIActionInProgress(KiaUvoEntity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        super().__init__(hass, config_entry, vehicle)
        self.topic_update = TOPIC_UPDATE.format(f"API-AIP")
        self._is_on = False
        self._is_available = False
        self._name = None

    @property
    def unique_id(self):
        return f"{DOMAIN}-API-action-in-progress"

    @property
    def device_class(self):
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return "mdi:api" if self.is_on else "mdi:api-off"

    @property
    def state(self):
        return "on" if self.is_on else "off"

    @property
    def available(self) -> bool:
        return self._is_available

    @property
    def is_on(self) -> bool:
        return self._is_on

    @callback
    def update_from_latest_data(self):
        vehicle = self.hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
        self._is_on = (
            not not vehicle
            and vehicle.kia_uvo_api.action_status_in_progress()
        )
        self._is_available = not not vehicle and vehicle.kia_uvo_api.last_action_tracked
        self._name = f"API Action ({vehicle.kia_uvo_api.last_action_name})"
