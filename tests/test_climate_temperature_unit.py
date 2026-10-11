"""Hyundai USA pending targets must stay in the backend's Fahrenheit unit."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_conversion import TemperatureConverter
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo.climate import HyundaiKiaCarClimateControlSwitch


def _entity(
    region: int = 3,
    brand: int = 2,
    unit: UnitOfTemperature | None = None,
) -> HyundaiKiaCarClimateControlSwitch:
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = False
    vehicle.air_temperature = (None, unit)
    vehicle.defrost_is_on = False
    vehicle.steering_wheel_heater_is_on = False
    vehicle.back_window_heater_is_on = False

    coordinator = MagicMock()
    coordinator.vehicle_manager.region = region
    coordinator.vehicle_manager.brand = brand
    coordinator.async_start_climate = AsyncMock()
    coordinator.async_stop_climate = AsyncMock()
    entity = HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    return entity


def test_hyundai_usa_unknown_temperature_has_fahrenheit_capabilities() -> None:
    entity = _entity()

    assert entity.target_temperature is None
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.min_temp == 62
    assert entity.max_temp == 82
    assert entity.target_temperature_step == 1


async def test_pending_target_survives_first_fahrenheit_status() -> None:
    """Do not store 70°F as 21.1°C and later send that scalar as Fahrenheit."""
    entity = _entity()
    # HA converts display-unit targets to the entity's native unit.
    native_target = TemperatureConverter.convert(
        70, UnitOfTemperature.FAHRENHEIT, entity.temperature_unit
    )
    await entity.async_set_temperature(temperature=native_target)
    entity.coordinator.async_start_climate.assert_not_called()
    entity.coordinator.async_stop_climate.assert_not_called()

    entity.vehicle.air_temperature = (68, UnitOfTemperature.FAHRENHEIT)
    await entity.async_set_hvac_mode(HVACMode.AUTO)

    _vehicle_id, options = entity.coordinator.async_start_climate.call_args.args
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert options.set_temp == 70
    assert options.climate is True


@pytest.mark.parametrize(
    ("region", "brand", "unit", "expected_unit"),
    [
        (1, 2, None, UnitOfTemperature.CELSIUS),
        (1, 2, UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS),
        (2, 2, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.FAHRENHEIT),
        (3, 1, None, UnitOfTemperature.CELSIUS),
        (3, 1, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.FAHRENHEIT),
        (3, 3, None, UnitOfTemperature.CELSIUS),
    ],
)
async def test_other_backends_keep_unit_precision_and_pending_target(
    region: int,
    brand: int,
    unit: UnitOfTemperature | None,
    expected_unit: UnitOfTemperature,
) -> None:
    entity = _entity(region, brand, unit)

    assert entity.temperature_unit == expected_unit
    assert entity.target_temperature_step == 0.5
    await entity.async_set_temperature(temperature=21.5)
    assert entity.climate_config.set_temp == 21.5
    entity.coordinator.async_start_climate.assert_not_called()


def test_hyundai_usa_unit_remains_fahrenheit_after_status_dropout() -> None:
    entity = _entity(unit=UnitOfTemperature.FAHRENHEIT)
    entity.vehicle.air_temperature = ("OFF", None)

    assert entity.target_temperature is None
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.target_temperature_step == 1
