"""Tests that starting climate actually asks the car to switch climate on.

``ClimateRequestOptions.climate`` is serialised by the backends as the
``airCtrl`` field of the start-climate payload. It used to be seeded from
``vehicle.air_control_is_on``, which is False in exactly the situation where
a user reaches for the control -- climate is off and they want it on -- so the
integration sent a start request carrying ``airCtrl=0`` and the car correctly
did nothing.

This is easy to miss because the neighbouring code paths are unaffected: the
``kia_uvo.start_climate`` service builds its own options object and callers
pass ``climate: true`` explicitly, and the climate *switch* entity sends a
bare ``ClimateRequestOptions()`` whose ``climate=None`` the API library then
defaults to True. Only the climate entity carried the stale False through.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo import climate
from custom_components.kia_uvo.climate import HyundaiKiaCarClimateControlSwitch


@pytest.fixture(autouse=True)
def _no_restart_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the 5 s wait between stop and start on a temperature change."""
    monkeypatch.setattr(climate, "asyncio", MagicMock(sleep=AsyncMock()))


def _entity(air_control_is_on: bool) -> HyundaiKiaCarClimateControlSwitch:
    """A climate entity over a vehicle in the given air-control state."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = air_control_is_on
    # The setter takes a (value, unit) pair.
    vehicle.air_temperature = (21, "C")
    vehicle.defrost_is_on = False
    vehicle.steering_wheel_heater_is_on = False
    vehicle.back_window_heater_is_on = False

    coordinator = MagicMock()
    coordinator.async_start_climate = AsyncMock()
    coordinator.async_stop_climate = AsyncMock()

    entity = HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    return entity


async def test_start_requests_air_control_on_while_climate_is_off() -> None:
    """Starting from the off state must send climate=True, not the stale False."""
    entity = _entity(air_control_is_on=False)

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    _vehicle_id, options = entity.coordinator.async_start_climate.call_args.args
    assert options.climate is True


async def test_cool_also_requests_air_control_on() -> None:
    """The car has no mode of its own, so COOL is the same request as HEAT."""
    entity = _entity(air_control_is_on=False)

    await entity.async_set_hvac_mode(HVACMode.COOL)

    _vehicle_id, options = entity.coordinator.async_start_climate.call_args.args
    assert options.climate is True


async def test_off_stops_climate_and_does_not_start_it() -> None:
    """Turning off must reach stop_climate only."""
    entity = _entity(air_control_is_on=True)

    await entity.async_set_hvac_mode(HVACMode.OFF)

    entity.coordinator.async_stop_climate.assert_awaited_once_with("v1")
    entity.coordinator.async_start_climate.assert_not_called()


async def test_temperature_change_while_on_restarts_with_air_control_on() -> None:
    """The stop/start cycle must bring climate back up, not just stop it.

    This path happened to be safe before the fix, because it can only run
    while climate is already on and the request was seeded True in that case.
    Pinned so the invariant survives future edits.
    """
    entity = _entity(air_control_is_on=True)

    await entity.async_set_temperature(temperature=23)

    entity.coordinator.async_stop_climate.assert_awaited_once_with("v1")
    _vehicle_id, options = entity.coordinator.async_start_climate.call_args.args
    assert options.climate is True
    assert options.set_temp == 23


async def test_turn_on_off_are_supported() -> None:
    """Without these flags climate.turn_on/turn_off reject the entity."""
    entity = _entity(air_control_is_on=False)

    assert entity.supported_features & ClimateEntityFeature.TURN_ON
    assert entity.supported_features & ClimateEntityFeature.TURN_OFF


async def test_turn_on_and_off_route_to_the_car() -> None:
    entity = _entity(air_control_is_on=False)

    await entity.async_turn_on()
    _vehicle_id, options = entity.coordinator.async_start_climate.call_args.args
    assert options.climate is True

    await entity.async_turn_off()
    entity.coordinator.async_stop_climate.assert_awaited_once_with("v1")
