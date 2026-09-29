"""Tests for action button description logic.

Exercises the exists_fn / enabled_fn predicates so we can assert which buttons
are created and which are disabled by default without full HA entity setup.
"""

from unittest.mock import MagicMock

import pytest

from custom_components.kia_uvo.button import (
    BUTTON_DESCRIPTIONS,
    HyundaiKiaButtonDescription,
)


def _find_description(key: str) -> HyundaiKiaButtonDescription:
    for description in BUTTON_DESCRIPTIONS:
        if description.key == key:
            return description
    raise AssertionError(f"description {key} not found")


def _make_vehicle(front_left_window_is_open=None) -> MagicMock:
    vehicle = MagicMock()
    vehicle.front_left_window_is_open = front_left_window_is_open
    return vehicle


class TestButtonExistsFn:
    @pytest.mark.asyncio
    async def test_window_buttons_exist_when_window_state_reported(self):
        vehicle = _make_vehicle(front_left_window_is_open=0)
        for key in ("open_all_windows", "close_all_windows", "vent_all_windows"):
            description = _find_description(key)
            assert description.exists_fn(vehicle) is True

    @pytest.mark.asyncio
    async def test_window_buttons_do_not_exist_when_no_window_state(self):
        vehicle = _make_vehicle(front_left_window_is_open=None)
        for key in ("open_all_windows", "close_all_windows", "vent_all_windows"):
            description = _find_description(key)
            assert description.exists_fn(vehicle) is False

    @pytest.mark.asyncio
    async def test_hazard_and_horn_always_exist(self):
        vehicle = _make_vehicle(front_left_window_is_open=None)
        for key in ("start_hazard_lights", "start_hazard_lights_and_horn"):
            description = _find_description(key)
            assert description.exists_fn(vehicle) is True


class TestButtonEnabledFn:
    @pytest.mark.asyncio
    async def test_window_buttons_enabled_by_default(self):
        vehicle = _make_vehicle(front_left_window_is_open=0)
        for key in ("open_all_windows", "close_all_windows", "vent_all_windows"):
            description = _find_description(key)
            assert description.enabled_fn(vehicle) is True

    @pytest.mark.asyncio
    async def test_hazard_and_horn_disabled_by_default(self):
        vehicle = _make_vehicle(front_left_window_is_open=0)
        for key in ("start_hazard_lights", "start_hazard_lights_and_horn"):
            description = _find_description(key)
            assert description.enabled_fn(vehicle) is False

    @pytest.mark.asyncio
    async def test_force_refresh_enabled_by_default(self):
        vehicle = _make_vehicle()
        description = _find_description("force_refresh")
        assert description.enabled_fn(vehicle) is True
