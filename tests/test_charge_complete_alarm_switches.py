"""Tests for the charge-complete alarm switches (multi-select, 1909)."""

from hyundai_kia_connect_api import Vehicle

KEYS = (
    "ev_charge_complete_alarm_before_10min",
    "ev_charge_complete_alarm_before_20min",
    "ev_charge_complete_alarm_before_30min",
)


def _vehicle(**flags):
    vehicle = Vehicle(id="v1", name="test", model="test")
    for attribute, value in flags.items():
        setattr(vehicle, attribute, value)
    return vehicle


async def test_absent_block_creates_no_switches(setup_switches) -> None:
    """No alarm block, no entities."""
    created = await setup_switches(_vehicle())
    assert all(key not in created for key in KEYS)


async def test_combos_are_independent_switches(setup_switches) -> None:
    """The PV5 wallbox combo (10min + 30min on, 20min off) stands."""
    created = await setup_switches(
        _vehicle(
            ev_charge_complete_alarm_before_10min=True,
            ev_charge_complete_alarm_before_20min=False,
            ev_charge_complete_alarm_before_30min=True,
        )
    )
    assert created["ev_charge_complete_alarm_before_10min"].is_on is True
    assert created["ev_charge_complete_alarm_before_20min"].is_on is False
    assert created["ev_charge_complete_alarm_before_30min"].is_on is True


async def test_toggles_call_the_coordinator_with_the_offset(
    setup_switches,
) -> None:
    """Toggling one offset sends (vid, minutes, enabled) to the coordinator."""
    created = await setup_switches(
        _vehicle(
            ev_charge_complete_alarm_before_10min=True,
            ev_charge_complete_alarm_before_20min=False,
            ev_charge_complete_alarm_before_30min=False,
        )
    )
    switch = created["ev_charge_complete_alarm_before_20min"]
    await switch.async_turn_on()
    switch.coordinator.async_set_charge_alarm_before.assert_awaited_with("v1", 20, True)
    await switch.async_turn_off()
    switch.coordinator.async_set_charge_alarm_before.assert_awaited_with(
        "v1", 20, False
    )
