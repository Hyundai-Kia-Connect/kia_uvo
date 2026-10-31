"""Tests for the charge-complete-alarm sensor value function."""

from hyundai_kia_connect_api import Vehicle
import pytest


@pytest.fixture
def alarm_entity(setup_sensors):
    async def _entity(**flags: bool | None):
        vehicle = Vehicle(id="v1", name="test", model="test")
        for attribute, value in flags.items():
            setattr(vehicle, attribute, value)
        return (await setup_sensors(vehicle)).get("ev_charge_complete_alarm")

    return _entity


async def test_absent_block_creates_no_entity(alarm_entity) -> None:
    """No alarm flags at all, no entity."""
    assert await alarm_entity() is None


async def test_each_flag_maps_to_its_preset(alarm_entity) -> None:
    """The preset of the set flag is the state."""
    cases = {
        "ev_charge_complete_alarm_before_10min": "before_10min",
        "ev_charge_complete_alarm_before_20min": "before_20min",
        "ev_charge_complete_alarm_before_30min": "before_30min",
        "ev_charge_complete_alarm_off": "off",
    }
    for flag, preset in cases.items():
        entity = await alarm_entity(**{flag: True})
        assert entity is not None
        assert entity.native_value == preset


async def test_false_flags_are_not_the_preset(alarm_entity) -> None:
    """False flags are served-but-unset; a True flag wins over them."""
    entity = await alarm_entity(
        ev_charge_complete_alarm_before_10min=False,
        ev_charge_complete_alarm_off=True,
    )
    assert entity is not None
    assert entity.native_value == "off"
