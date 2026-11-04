"""Tests for the climate-duration select and its wiring into climate starts.

The climate entity and the start-climate switch used to start the car without
a duration, so the lib's 5-minute default applied and no one could change it
(kia_uvo#2063). The select stores a per-vehicle preference (or "auto"; "auto"
keeps the lib default, i.e. the previous behaviour) and the start paths read
it when building ``ClimateRequestOptions``.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.climate.const import HVACMode
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo.const import CLIMATE_DURATION_AUTO
from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator


def _coordinator() -> HyundaiKiaConnectDataUpdateCoordinator:
    """A coordinator with the duration-store attributes initialized."""
    coordinator = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    coordinator._climate_duration_options = {}
    return coordinator


def test_duration_defaults_to_auto() -> None:
    """With no selection the start paths get None, i.e. the lib default."""
    coordinator = _coordinator()

    assert coordinator.get_climate_duration_option("v1") == CLIMATE_DURATION_AUTO
    assert coordinator.climate_duration_value("v1") is None


async def test_default_start_honours_selection() -> None:
    """async_start_climate_default must pass the selected duration on."""
    coordinator = _coordinator()
    coordinator.vehicle_manager = MagicMock()
    coordinator.vehicle_manager.start_climate = AsyncMock()
    coordinator._async_send_action = AsyncMock()

    async def _call(
        _vehicle_id: str,
        action_fn: Any,
        *_args: Any,
        **_kwargs: Any,
    ) -> None:
        await action_fn()

    coordinator._async_send_action.side_effect = _call
    coordinator.set_climate_duration_option("v1", "15")

    await coordinator.async_start_climate_default("v1")

    _vehicle_id, options = coordinator.vehicle_manager.start_climate.call_args.args
    assert options.duration == 15


async def test_climate_entity_injects_duration() -> None:
    """The climate entity passes the selected duration into start_climate."""
    import custom_components.kia_uvo.climate as climate_module

    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = False
    vehicle.air_temperature = (21, "C")
    vehicle.defrost_is_on = False
    vehicle.steering_wheel_heater_is_on = False
    vehicle.back_window_heater_is_on = False

    coordinator = MagicMock()
    coordinator.climate_duration_value.return_value = 30
    coordinator.async_start_climate = AsyncMock()
    coordinator.async_stop_climate = AsyncMock()

    entity = climate_module.HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    _vehicle_id, options = coordinator.async_start_climate.call_args.args
    assert options.duration == 30


def test_duration_option_roundtrip() -> None:
    """The select stores the raw option; the value resolver maps "auto" to None."""
    coordinator = _coordinator()

    coordinator.set_climate_duration_option("v1", "30")
    assert coordinator.get_climate_duration_option("v1") == "30"
    assert coordinator.climate_duration_value("v1") == 30

    coordinator.set_climate_duration_option("v1", CLIMATE_DURATION_AUTO)
    assert coordinator.climate_duration_value("v1") is None
