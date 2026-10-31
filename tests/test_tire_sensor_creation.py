"""Tests for numeric tire-pressure sensor creation gating.

On backends where TPMS is transient (confirmed live on AU/NZ), the cached
state carries the 255 no-data sentinel (parsed to None) whenever the car is
parked — nearly always the case at integration setup — so gating creation on
the value would mean the sensors never exist. Creation is gated on the parsed
``vehicle.tire_pressure_unit`` instead: non-None exactly for direct-TPMS
vehicles, None for indirect-TPMS vehicles (PressureUnit 3, e.g. the KONA EV
dump in kia_uvo #1786) and old-protocol vehicles, which can never report a
numeric pressure.

The payload fixtures run through the REAL API-library CCS2 parser so these
tests pin the whole contract, not a re-implementation of it.
"""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.sensor import SensorExtraStoredData
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.KiaUvoApiAU import KiaUvoApiAU


def _ccs2_state(pressure_unit: int, tire_pressure: int) -> dict:
    """Minimal CCS2 cached-state payload the real parser accepts.

    The Chassis.Axle section carries the scenario under test; Drivetrain
    holds the baseline fields the parser reads without a None guard.
    """
    tire = {"Tire": {"Pressure": tire_pressure, "PressureLow": 0}}
    return {
        "Chassis": {
            "Axle": {
                "Row1": {"Left": dict(tire), "Right": dict(tire)},
                "Row2": {"Left": dict(tire), "Right": dict(tire)},
                "Tire": {"PressureUnit": pressure_unit, "PressureLow": 0},
            }
        },
        "Drivetrain": {"FuelSystem": {"DTE": {"Total": 0, "Unit": 1}}},
    }


# Real AU/NZ shape while parked: direct TPMS (PressureUnit 0 = psi),
# pressures at the 255 no-data sentinel.
_DIRECT_TPMS_PARKED = _ccs2_state(pressure_unit=0, tire_pressure=255)

# AU/NZ shape while driving: valid pressure readings (e.g. 34 psi).
_DIRECT_TPMS_DRIVING = _ccs2_state(pressure_unit=0, tire_pressure=34)

# KONA EV shape from kia_uvo #1786: indirect TPMS (PressureUnit 3), no direct
# sensors — the vehicle can never report a per-tire pressure.
_INDIRECT_TPMS = _ccs2_state(pressure_unit=3, tire_pressure=0)


def _parsed_vehicle(state: dict | None) -> Vehicle:
    """A real Vehicle run through the real CCS2 parser (no network)."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.ccu_ccs2_protocol_support = 1
    if state is not None:
        api = KiaUvoApiAU(region=5, brand=2, language="en")
        api._update_vehicle_properties_ccs2(vehicle, state)
    return vehicle


async def _created_tire_keys(setup_sensors, vehicle: Vehicle) -> list[str]:
    """Run the real async_setup_entry and return created tire sensor keys."""
    return [k for k in await setup_sensors(vehicle) if k.startswith("tire_pressure_")]


async def test_direct_tpms_parked_creates_sensors(setup_sensors) -> None:
    """Direct TPMS with the parked 255 sentinel -> all 4 sensors created."""
    vehicle = _parsed_vehicle(_DIRECT_TPMS_PARKED)
    assert vehicle.tire_pressure_unit is not None
    assert vehicle.tire_pressure_front_left is None  # sentinel parsed to None
    assert len(await _created_tire_keys(setup_sensors, vehicle)) == 4


async def test_indirect_tpms_kona_creates_no_sensors(setup_sensors) -> None:
    """PressureUnit 3 (indirect TPMS, KONA shape from #1786) -> no sensors."""
    vehicle = _parsed_vehicle(_INDIRECT_TPMS)
    assert vehicle.tire_pressure_unit is None
    assert await _created_tire_keys(setup_sensors, vehicle) == []


async def test_no_tpms_data_creates_no_sensors(setup_sensors) -> None:
    """Vehicle never parsed through the CCS2 path (old protocol) -> none."""
    vehicle = _parsed_vehicle(None)
    assert vehicle.tire_pressure_unit is None
    assert await _created_tire_keys(setup_sensors, vehicle) == []


async def test_tire_pressure_sensor_retains_last_known_value_when_parked(
    setup_sensors,
) -> None:
    """Sensor retains its last reported reading when car parks (None sentinel)."""
    vehicle = _parsed_vehicle(_DIRECT_TPMS_DRIVING)
    sensors = await setup_sensors(vehicle)
    sensor = sensors["tire_pressure_front_left"]
    assert sensor.native_value == 34
    assert sensor.native_unit_of_measurement == "psi"

    # Car parks: telematics sends 255 sentinel (parsed to None)
    api = KiaUvoApiAU(region=5, brand=2, language="en")
    api._update_vehicle_properties_ccs2(vehicle, _DIRECT_TPMS_PARKED)
    assert vehicle.tire_pressure_front_left is None
    # Sensor retains the last known value and unit while parked
    assert sensor.native_value == 34
    assert sensor.native_unit_of_measurement == "psi"

    # Car drives again: new live reading updates sensor
    api._update_vehicle_properties_ccs2(
        vehicle, _ccs2_state(pressure_unit=0, tire_pressure=36)
    )
    assert sensor.native_value == 36


async def test_tire_pressure_sensor_restores_from_last_sensor_data(
    setup_sensors,
) -> None:
    """Sensor restores its last known value and unit after Home Assistant restart."""
    vehicle = _parsed_vehicle(_DIRECT_TPMS_PARKED)
    sensors = await setup_sensors(vehicle)
    sensor = sensors["tire_pressure_front_left"]
    assert sensor.native_value is None

    sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SensorExtraStoredData(
            native_value=33.5, native_unit_of_measurement="psi"
        )
    )
    await sensor.async_added_to_hass()
    assert sensor.native_value == 33.5
    assert sensor.native_unit_of_measurement == "psi"


async def test_tire_pressure_sensor_restores_from_last_state_fallback(
    setup_sensors,
) -> None:
    """Sensor restores from last state when extra sensor data is unavailable."""
    vehicle = _parsed_vehicle(_DIRECT_TPMS_PARKED)
    sensors = await setup_sensors(vehicle)
    sensor = sensors["tire_pressure_front_left"]
    assert sensor.native_value is None

    sensor.async_get_last_sensor_data = AsyncMock(return_value=None)
    sensor.async_get_last_state = AsyncMock(return_value=MagicMock(state="34.0"))
    await sensor.async_added_to_hass()
    assert sensor.native_value == 34.0
