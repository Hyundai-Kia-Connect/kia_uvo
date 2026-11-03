"""Creation gating for the GSPA stored-status sensor extras (kia_uvo #1913)."""

from hyundai_kia_connect_api import Vehicle
import pytest

V2L_KEYS = (
    "ev_v2l_discharge_remain_time",
    "ev_v2l_discharge_dte",
    "ev_v2l_mode",
)
FUEL_KEYS = (
    "average_fuel_economy_accumulated",
    "average_fuel_economy_drive",
    "average_fuel_economy_after_refuel",
)


@pytest.fixture
def make_vehicle():
    def _vehicle(**fields):
        vehicle = Vehicle(id="v1", name="test", model="test")
        for attribute, value in fields.items():
            setattr(vehicle, attribute, value)
        return vehicle

    return _vehicle


async def test_v2l_sensors_created_only_with_the_block(setup_sensors, make_vehicle):
    """No V2L block, no V2L entities."""
    created = await setup_sensors(make_vehicle())
    assert not any(key in created for key in V2L_KEYS)


async def test_v2l_sensors_stay_when_one_field_is_none(
    setup_sensors, make_vehicle
) -> None:
    """A None field inside a served block reports unknown, not no entity."""
    created = await setup_sensors(make_vehicle(ev_v2l_discharge_limit=50))
    assert all(key in created for key in V2L_KEYS)
    assert created["ev_v2l_mode"].native_value is None


async def test_fuel_economy_sensors_created_only_with_unit(
    setup_sensors, make_vehicle
) -> None:
    """The unit field is the proof the backend serves fuel-economy data."""
    created = await setup_sensors(make_vehicle(average_fuel_economy_accumulated=6.4))
    assert not any(key in created for key in FUEL_KEYS)

    created = await setup_sensors(
        make_vehicle(average_fuel_economy_unit=2, average_fuel_economy_drive=5.9)
    )
    assert all(key in created for key in FUEL_KEYS)


async def test_gear_and_steering_step_created_only_with_value(
    setup_sensors, make_vehicle
) -> None:
    """Raw stored-status fields gate on their own presence."""
    created = await setup_sensors(make_vehicle())
    assert "gear_position" not in created
    assert "steering_wheel_heat_step" not in created

    created = await setup_sensors(
        make_vehicle(gear_position=2, steering_wheel_heat_step=1)
    )
    assert created["gear_position"].native_value == 2
    assert created["steering_wheel_heat_step"].native_value == 1
