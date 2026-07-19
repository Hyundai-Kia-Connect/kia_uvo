"""Tests for numeric tire-pressure sensor creation gating.

On backends where TPMS is transient (confirmed live on AU/NZ), the cached
state carries the 255 no-data sentinel (parsed to None) whenever the car is
parked — nearly always the case at integration setup — so gating creation on
the value would mean the sensors never exist. Creation must instead be gated
on the CCS2 tire structure being present in the raw vehicle data.
"""

from unittest.mock import MagicMock

from custom_components.kia_uvo.sensor import _tire_pressure_sensor_supported

# Shape of the real AU/NZ CCS2 payload while parked: structure present,
# pressures at the 255 sentinel (which the API library parses to None).
_CCS2_PARKED_DATA = {
    "Chassis": {
        "Axle": {
            "Row1": {
                "Left": {"Tire": {"Pressure": 255, "PressureLow": 0}},
                "Right": {"Tire": {"Pressure": 255, "PressureLow": 0}},
            },
            "Row2": {
                "Left": {"Tire": {"Pressure": 255, "PressureLow": 0}},
                "Right": {"Tire": {"Pressure": 255, "PressureLow": 0}},
            },
            "Tire": {"PressureUnit": 0, "PressureLow": 0},
        }
    }
}


def _make_vehicle(ccs2=1, data=None, pressure=None) -> MagicMock:
    vehicle = MagicMock()
    vehicle.ccu_ccs2_protocol_support = ccs2
    vehicle.data = data if data is not None else {}
    vehicle.tire_pressure_front_left = pressure
    vehicle.tire_pressure_front_right = pressure
    vehicle.tire_pressure_rear_left = pressure
    vehicle.tire_pressure_rear_right = pressure
    return vehicle


def test_ccs2_parked_car_supported() -> None:
    """CCS2 structure present but values at the sentinel -> supported."""
    vehicle = _make_vehicle(ccs2=1, data=_CCS2_PARKED_DATA, pressure=None)
    assert _tire_pressure_sensor_supported(vehicle) is True


def test_non_ccs2_not_supported() -> None:
    """Old-protocol vehicles (warning lamps only) -> not supported."""
    vehicle = _make_vehicle(ccs2=0, data={}, pressure=None)
    assert _tire_pressure_sensor_supported(vehicle) is False


def test_ccs2_without_tire_structure_not_supported() -> None:
    """CCS2 vehicle whose payload has no tire structure -> not supported."""
    vehicle = _make_vehicle(ccs2=1, data={"Chassis": {"Axle": {}}}, pressure=None)
    assert _tire_pressure_sensor_supported(vehicle) is False
