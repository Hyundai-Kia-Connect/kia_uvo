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

from unittest.mock import MagicMock

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.KiaUvoApiAU import KiaUvoApiAU

from custom_components.kia_uvo import sensor as sensor_platform
from custom_components.kia_uvo.const import DOMAIN


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


async def _created_tire_keys(vehicle: Vehicle) -> list[str]:
    """Run the real async_setup_entry and return created tire sensor keys."""
    coordinator = MagicMock()
    coordinator.vehicle_manager.vehicles = {"v1": vehicle}
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.unique_id = "uid"
    hass.data = {DOMAIN: {"uid": coordinator}}
    created = []
    await sensor_platform.async_setup_entry(hass, config_entry, created.extend)
    return [
        entity.entity_description.key
        for entity in created
        if getattr(entity, "entity_description", None) is not None
        and entity.entity_description.key.startswith("tire_pressure_")
    ]


async def test_direct_tpms_parked_creates_sensors() -> None:
    """Direct TPMS with the parked 255 sentinel -> all 4 sensors created."""
    vehicle = _parsed_vehicle(_DIRECT_TPMS_PARKED)
    assert vehicle.tire_pressure_unit is not None
    assert vehicle.tire_pressure_front_left is None  # sentinel parsed to None
    assert len(await _created_tire_keys(vehicle)) == 4


async def test_indirect_tpms_kona_creates_no_sensors() -> None:
    """PressureUnit 3 (indirect TPMS, KONA shape from #1786) -> no sensors."""
    vehicle = _parsed_vehicle(_INDIRECT_TPMS)
    assert vehicle.tire_pressure_unit is None
    assert await _created_tire_keys(vehicle) == []


async def test_no_tpms_data_creates_no_sensors() -> None:
    """Vehicle never parsed through the CCS2 path (old protocol) -> none."""
    vehicle = _parsed_vehicle(None)
    assert vehicle.tire_pressure_unit is None
    assert await _created_tire_keys(vehicle) == []
