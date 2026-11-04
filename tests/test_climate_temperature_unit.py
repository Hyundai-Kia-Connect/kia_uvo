"""The climate entity's unit and step, including before the car reports a unit."""

from unittest.mock import MagicMock

from homeassistant.const import UnitOfTemperature
from hyundai_kia_connect_api import Vehicle
import pytest

from custom_components.kia_uvo.climate import HyundaiKiaCarClimateControlSwitch


def _entity(
    car_unit: str | None, ha_unit: UnitOfTemperature | None
) -> HyundaiKiaCarClimateControlSwitch:
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = False
    vehicle.air_temperature = (None, car_unit)
    entity = HyundaiKiaCarClimateControlSwitch(MagicMock(), vehicle)
    if ha_unit is not None:
        entity.hass = MagicMock()
        entity.hass.config.units.temperature_unit = ha_unit
    return entity


@pytest.mark.parametrize(
    ("ha_unit", "min_temp", "max_temp"),
    [(UnitOfTemperature.FAHRENHEIT, 62, 82), (UnitOfTemperature.CELSIUS, 14, 30)],
)
def test_unknown_car_unit_uses_ha_unit(ha_unit, min_temp, max_temp) -> None:
    entity = _entity(None, ha_unit)
    assert entity.native_temperature_unit == ha_unit
    assert (entity.min_temp, entity.max_temp) == (min_temp, max_temp)


def test_car_unit_wins_over_ha_unit() -> None:
    entity = _entity(UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS)
    assert entity.native_temperature_unit == UnitOfTemperature.FAHRENHEIT


def test_unknown_car_unit_before_attach_is_celsius() -> None:
    assert _entity(None, None).native_temperature_unit == UnitOfTemperature.CELSIUS


@pytest.mark.parametrize(
    ("car_unit", "ha_unit", "step"),
    [
        (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS, 1),
        (UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT, 0.5),
        (None, UnitOfTemperature.FAHRENHEIT, 1),
        (None, UnitOfTemperature.CELSIUS, 0.5),
    ],
)
def test_step_follows_unit(car_unit, ha_unit, step) -> None:
    assert _entity(car_unit, ha_unit).target_temperature_step == step
