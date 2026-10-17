"""Use library climate capabilities without depending on first telemetry."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_conversion import TemperatureConverter
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo.climate import HyundaiKiaCarClimateControlSwitch


def _entity(
    unit: UnitOfTemperature | None = None,
    native_unit: UnitOfTemperature | None = UnitOfTemperature.FAHRENHEIT,
    native_step: float | None = 1.0,
    display_unit: UnitOfTemperature = UnitOfTemperature.FAHRENHEIT,
    legacy: bool = False,
) -> HyundaiKiaCarClimateControlSwitch:
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = False
    vehicle.air_temperature = (None, unit)
    vehicle.defrost_is_on = False
    vehicle.steering_wheel_heater_is_on = False
    vehicle.back_window_heater_is_on = False
    if legacy:
        # An old library's Vehicle genuinely has neither new attribute.
        vehicle = SimpleNamespace(
            **{
                key: value
                for key, value in vars(vehicle).items()
                if not key.startswith("climate_temperature_")
            }
        )
        vehicle.air_temperature = None
    else:
        vehicle.climate_temperature_unit = native_unit
        vehicle.climate_temperature_step = native_step

    coordinator = MagicMock()
    coordinator.async_start_climate = AsyncMock()
    coordinator.async_stop_climate = AsyncMock()
    entity = HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)
    entity.hass = MagicMock()
    entity.hass.config.units.temperature_unit = display_unit
    entity.async_write_ha_state = MagicMock()
    return entity


def test_unknown_temperature_has_library_capabilities() -> None:
    entity = _entity()

    assert entity.target_temperature is None
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.min_temp == 62
    assert entity.max_temp == 82
    assert entity.target_temperature_step == 1
    assert entity.capability_attributes["target_temp_step"] == 1


@pytest.mark.parametrize(
    "display_unit", [UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS]
)
async def test_pending_target_survives_first_fahrenheit_status(display_unit) -> None:
    """HA display conversion must not change the backend's pending scalar."""
    entity = _entity(display_unit=display_unit)
    display_target = TemperatureConverter.convert(
        70, UnitOfTemperature.FAHRENHEIT, display_unit
    )
    native_target = TemperatureConverter.convert(
        display_target, display_unit, entity.temperature_unit
    )
    await entity.async_set_temperature(temperature=native_target)
    entity.coordinator.async_start_climate.assert_not_called()
    entity.coordinator.async_stop_climate.assert_not_called()

    entity.vehicle.air_temperature = (68, UnitOfTemperature.FAHRENHEIT)
    await entity.async_set_hvac_mode(HVACMode.AUTO)

    _vehicle_id, options = entity.coordinator.async_start_climate.call_args.args
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert options.set_temp == pytest.approx(70)
    assert options.climate is True


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize(
    ("unit", "expected_unit"),
    [
        (None, UnitOfTemperature.CELSIUS),
        (UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS),
        (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.FAHRENHEIT),
    ],
)
async def test_unspecified_capabilities_preserve_existing_behavior(
    legacy, unit, expected_unit
) -> None:
    entity = _entity(unit=unit, native_unit=None, native_step=None, legacy=legacy)

    assert entity.temperature_unit == expected_unit
    assert entity.target_temperature_step == 0.5
    await entity.async_set_temperature(temperature=21.5)
    assert entity.climate_config.set_temp == 21.5
    entity.coordinator.async_start_climate.assert_not_called()


def test_capabilities_survive_status_dropout() -> None:
    entity = _entity(unit=UnitOfTemperature.FAHRENHEIT)
    entity.vehicle.air_temperature = ("OFF", None)

    assert entity.target_temperature is None
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.target_temperature_step == 1


def test_native_step_is_converted_to_display_unit_as_interval() -> None:
    entity = _entity(display_unit=UnitOfTemperature.CELSIUS)

    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.target_temperature_step == pytest.approx(5 / 9)
    assert entity.capability_attributes["target_temp_step"] == pytest.approx(5 / 9)


def test_step_before_entity_attachment_uses_native_unit() -> None:
    entity = _entity()
    entity.hass = None

    assert entity.target_temperature_step == 1


def test_consumes_capabilities_without_backend_checks() -> None:
    entity = _entity(native_unit=UnitOfTemperature.CELSIUS, native_step=0.25)
    entity.hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

    assert entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.target_temperature_step == 0.25
