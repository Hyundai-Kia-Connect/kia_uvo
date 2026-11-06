"""Tests for the charge-complete alarm toggles (multi-select, 1909)."""

from hyundai_kia_connect_api import Vehicle

KEYS = (
    "ev_charge_complete_alarm_before_10min",
    "ev_charge_complete_alarm_before_20min",
    "ev_charge_complete_alarm_before_30min",
    "ev_charge_complete_alarm_off",
)


def _vehicle(**flags):
    vehicle = Vehicle(id="v1", name="test", model="test")
    for attribute, value in flags.items():
        setattr(vehicle, attribute, value)
    return vehicle


async def test_absent_block_creates_no_toggles(setup_binary_sensors) -> None:
    """No alarm block, no entities."""
    created = await setup_binary_sensors(_vehicle())
    assert all(key not in created for key in KEYS)


async def test_combos_are_independent_toggles(setup_binary_sensors) -> None:
    """The PV5 wallbox combo (10min + 30min on, 20min off) stands."""
    created = await setup_binary_sensors(
        _vehicle(
            ev_charge_complete_alarm_before_10min=True,
            ev_charge_complete_alarm_before_20min=False,
            ev_charge_complete_alarm_before_30min=True,
            ev_charge_complete_alarm_off=False,
        )
    )
    assert created["ev_charge_complete_alarm_before_10min"].is_on is True
    assert created["ev_charge_complete_alarm_before_20min"].is_on is False
    assert created["ev_charge_complete_alarm_before_30min"].is_on is True
    assert created["ev_charge_complete_alarm_off"].is_on is False


async def test_unset_sibling_creates_no_entity(setup_binary_sensors) -> None:
    """An unset flag (None) creates no entity (the default value gate)."""
    created = await setup_binary_sensors(
        _vehicle(ev_charge_complete_alarm_before_10min=True)
    )
    assert created["ev_charge_complete_alarm_before_10min"].is_on is True
    assert "ev_charge_complete_alarm_off" not in created
