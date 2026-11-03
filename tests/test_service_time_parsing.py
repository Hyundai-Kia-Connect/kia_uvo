"""Service time fields arrive as HH:MM:SS strings from HA's time selector."""

from datetime import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.kia_uvo import services


async def _call(
    monkeypatch: pytest.MonkeyPatch, service: str, data: dict[str, Any]
) -> MagicMock:
    coordinator = MagicMock()
    coordinator.async_set_off_peak_charging = AsyncMock()
    coordinator.async_schedule_charging_and_climate = AsyncMock()
    monkeypatch.setattr(
        services, "_get_coordinator_from_device", lambda *_: coordinator
    )
    monkeypatch.setattr(services, "_get_vehicle_id_from_device", lambda *_: "v1")

    hass = MagicMock()
    services.async_setup_services(hass)
    handlers = {
        c.args[1]: c.args[2] for c in hass.services.async_register.call_args_list
    }
    call = MagicMock()
    call.data = data
    await handlers[service](call)
    return coordinator


async def test_set_off_peak_charging_parses_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = await _call(
        monkeypatch,
        services.SERVICE_SET_OFF_PEAK_CHARGING,
        {"off_peak_start_time": "22:30:00", "off_peak_end_time": "06:00:00"},
    )
    coordinator.async_set_off_peak_charging.assert_awaited_once_with(
        "v1", mode=None, start=time(22, 30), end=time(6, 0)
    )


async def test_schedule_charging_and_climate_parses_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = await _call(
        monkeypatch,
        services.SERVICE_SCHEDULE_CHARGING_AND_CLIMATE,
        {
            "first_departure_time": "07:15:00",
            "off_peak_start_time": "22:30:00",
            "off_peak_end_time": "06:00:00",
        },
    )
    options = coordinator.async_schedule_charging_and_climate.await_args.args[1]
    assert options.first_departure.time == time(7, 15)
    assert options.second_departure.time is None
    assert options.off_peak_start_time == time(22, 30)
    assert options.off_peak_end_time == time(6, 0)
