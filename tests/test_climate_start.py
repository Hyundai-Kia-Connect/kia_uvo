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

from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature
from hyundai_kia_connect_api import Vehicle
import pytest

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


async def test_target_temperature_retains_setting_when_air_temp_is_none() -> None:
    """When vehicle air_temperature is None (HVAC off), target_temperature falls back to config."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = False
    vehicle.air_temperature = (None, "C")
    coordinator = MagicMock()
    coordinator.async_start_climate = AsyncMock()
    coordinator.async_stop_climate = AsyncMock()

    entity = HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    # Initial fallback
    assert entity.target_temperature == 21.0

    # User adjusts temperature via slider while off
    await entity.async_set_temperature(temperature=23.5)
    assert entity.target_temperature == 23.5
    coordinator.async_start_climate.assert_not_called()

    # Turning on now sends the user-chosen 23.5 target temp
    await entity.async_turn_on()
    _vehicle_id, options = entity.coordinator.async_start_climate.call_args.args
    assert options.climate is True
    assert options.set_temp == 23.5


async def test_set_temperature_with_hvac_mode_starts_climate() -> None:
    """Calling set_temperature with ATTR_HVAC_MODE starts climate with the given temperature."""
    entity = _entity(air_control_is_on=False)

    await entity.async_set_temperature(temperature=22.5, hvac_mode=HVACMode.AUTO)

    _vehicle_id, options = entity.coordinator.async_start_climate.call_args.args
    assert options.climate is True
    assert options.set_temp == 22.5


async def test_coordinator_update_syncs_set_temp_when_air_temperature_reported() -> (
    None
):
    """When vehicle reports air temperature, climate_config is updated."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = True
    vehicle.air_temperature = (24.0, "C")
    coordinator = MagicMock()
    coordinator.data = {}

    entity = HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    # Simulate coordinator update with new vehicle air_temperature
    vehicle.air_temperature = (25.5, "C")
    entity._handle_coordinator_update()
    assert entity.climate_config.set_temp == 25.5
    assert entity.target_temperature == 25.5


async def test_target_temperature_retains_setting_fahrenheit() -> None:
    """When vehicle uses Fahrenheit and air_temperature is None, target_temperature defaults to 72.0."""
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = False
    vehicle.air_temperature = (None, "F")
    coordinator = MagicMock()
    coordinator.async_start_climate = AsyncMock()

    entity = HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.target_temperature == 72.0

    # Ensure target_temperature fallback branch when climate_config has no set_temp
    entity.climate_config.set_temp = None
    assert entity.target_temperature == 72.0


async def test_temperature_unit_fallback_strings() -> None:
    """Verify fallback string handling for non-degree Celsius and Fahrenheit indicators."""
    vehicle_c = Vehicle(id="v1", name="test", model="test")
    vehicle_c.air_control_is_on = False
    vehicle_c.air_temperature = (None, "C")
    entity_c = HyundaiKiaCarClimateControlSwitch(MagicMock(), vehicle_c)
    assert entity_c.temperature_unit == UnitOfTemperature.CELSIUS

    vehicle_f = Vehicle(id="v2", name="test", model="test")
    vehicle_f.air_control_is_on = False
    vehicle_f.air_temperature = (None, "F")
    entity_f = HyundaiKiaCarClimateControlSwitch(MagicMock(), vehicle_f)
    assert entity_f.temperature_unit == UnitOfTemperature.FAHRENHEIT
