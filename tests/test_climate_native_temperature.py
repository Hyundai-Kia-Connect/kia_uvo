"""Native temperatures must retain vehicle units without deprecated reads."""

from unittest.mock import MagicMock

from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from hyundai_kia_connect_api import Vehicle
import pytest

from custom_components.kia_uvo.climate import HyundaiKiaCarClimateControlSwitch


@pytest.mark.parametrize(
    ("unit", "value", "ha_units", "bounds", "step", "displayed"),
    [
        (UnitOfTemperature.CELSIUS, 20, US_CUSTOMARY_SYSTEM, (14, 30), 0.5, 68),
        (UnitOfTemperature.FAHRENHEIT, 68, METRIC_SYSTEM, (62, 82), 1, 20),
    ],
)
def test_native_temperature_preserves_units_and_display(
    unit, value, ha_units, bounds, step, displayed, caplog
) -> None:
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = False
    vehicle.air_temperature = (value, unit)
    entity = HyundaiKiaCarClimateControlSwitch(MagicMock(), vehicle)
    entity.hass = MagicMock()
    entity.hass.config.units = ha_units

    caplog.clear()
    assert entity.native_temperature_unit == unit
    assert entity.native_target_temperature == value
    assert entity.native_current_temperature is None
    assert (entity.min_temp, entity.max_temp) == bounds
    assert entity.target_temperature_step == step
    assert entity.state_attributes["temperature"] == displayed
    assert not any("deprecated" in record.getMessage() for record in caplog.records)


def test_climate_import_uses_supported_temperature_api(caplog) -> None:
    import importlib

    from custom_components.kia_uvo import climate

    caplog.clear()
    importlib.reload(climate)
    assert not any(
        "provides the deprecated" in record.getMessage() for record in caplog.records
    )
