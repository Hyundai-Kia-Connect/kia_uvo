"""Japan command filtering must not alter established regional platforms."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import make_coordinator, make_hass
from homeassistant.exceptions import HomeAssistantError
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo import button, climate, lock, number, switch
from custom_components.kia_uvo.japan_coordinator import JapanDataUpdateCoordinator


async def test_japan_rejects_unsupported_service_before_authentication():
    result = JapanDataUpdateCoordinator.__new__(JapanDataUpdateCoordinator)
    result.vehicle_manager = MagicMock()
    result.vehicle_manager.api = SimpleNamespace(
        supported_commands=frozenset({"lock_action"})
    )
    result.async_check_and_refresh_token = AsyncMock()
    result.hass = MagicMock()
    result.hass.async_add_executor_job = AsyncMock()
    with pytest.raises(
        HomeAssistantError, match="does not support this vehicle command"
    ):
        await result.async_start_charge("synthetic")
    result.async_check_and_refresh_token.assert_not_awaited()
    result.hass.async_add_executor_job.assert_not_awaited()


async def test_japan_exposes_only_supported_commands():
    vehicle = Vehicle(id="synthetic", name="synthetic", model="synthetic")
    vehicle.air_control_is_on = False
    vehicle.ev_battery_is_charging = False
    vehicle.ev_charge_limits_ac = 80
    vehicle.ev_charge_limits_dc = 90
    vehicle.supports_svm = True
    coordinator = make_coordinator(vehicle)
    coordinator.__class__ = JapanDataUpdateCoordinator
    allowed = {
        "lock_action",
        "start_charge",
        "stop_charge",
        "set_charge_limits",
        "start_hazard_lights",
    }
    coordinator.supports_command = lambda command: command in allowed
    hass, entry = make_hass(coordinator)
    entities = {}
    for platform in (lock, climate, number, switch, button):
        created = []
        await platform.async_setup_entry(
            hass, entry, lambda values, *args, target=created: target.extend(values)
        )
        entities[platform.__name__.rsplit(".", 1)[-1]] = created
    assert len(entities["lock"]) == 1
    assert entities["climate"] == []
    assert {e.entity_description.key for e in entities["number"]} == {
        "ev_charge_limits_ac",
        "ev_charge_limits_dc",
    }
    assert {e.entity_description.key for e in entities["button"]} == {
        "force_refresh",
        "start_hazard_lights",
    }
    assert any(isinstance(e, switch.SVMDewarpSwitch) for e in entities["switch"])


@pytest.mark.parametrize("platform", [lock, climate, number, button])
async def test_non_japan_platforms_ignore_new_japan_capabilities(platform):
    vehicle = Vehicle(id="synthetic", name="synthetic", model="synthetic")
    vehicle.air_control_is_on = False
    vehicle.ev_charge_limits_ac = 80
    coordinator = make_coordinator(vehicle)
    # These attributes are irrelevant to the established regional coordinator.
    coordinator.supports_command = lambda _: False
    coordinator.supports_remote_commands = False
    coordinator.supports_force_refresh = False
    hass, entry = make_hass(coordinator)
    created = []
    await platform.async_setup_entry(
        hass, entry, lambda values, *args, target=created: target.extend(values)
    )
    assert created
