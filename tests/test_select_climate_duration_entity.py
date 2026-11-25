"""Tests for the climate-duration select entity and its gating.

The select is created per vehicle where the lib reports the duration
setting, keeps its option on the coordinator ("auto" = lib default) and
sends nothing to the car on selection.
"""

import asyncio
from typing import Any
from unittest.mock import MagicMock

from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo.const import CLIMATE_DURATION_AUTO, DOMAIN
from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator
from custom_components.kia_uvo.select import (
    SELECT_DESCRIPTIONS,
    HyundaiKiaConnectSelectEntity,
    async_setup_entry,
)


def _coordinator() -> HyundaiKiaConnectDataUpdateCoordinator:
    coordinator = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    coordinator._climate_duration_options = {}
    coordinator.vehicle_manager = MagicMock()
    return coordinator


def _vehicle(duration_setting: bool | None) -> Vehicle:
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.supports.climate_duration_setting = duration_setting
    return vehicle


def test_select_created_only_when_flag_is_true() -> None:
    """The exists gate: True creates, False and None do not."""
    description = SELECT_DESCRIPTIONS[0]
    coordinator = _coordinator()

    assert description.exists_fn(_vehicle(True)) is True
    assert description.exists_fn(_vehicle(False)) is False
    assert description.exists_fn(_vehicle(None)) is False

    coordinator.vehicle_manager.vehicles = {
        "v1": _vehicle(True),
        "v2": _vehicle(False),
    }

    added: list[Any] = []

    def _capture(entities: list[Any]) -> None:
        added.extend(entities)

    hass = MagicMock()
    hass.data = {DOMAIN: {"entry-1": coordinator}}
    entry = MagicMock()
    entry.unique_id = "entry-1"

    asyncio.run(async_setup_entry(hass, entry, _capture))

    assert [e.vehicle.id for e in added] == ["v1"]


def test_select_default_is_auto_and_set_stores_option() -> None:
    coordinator = _coordinator()
    entity = HyundaiKiaConnectSelectEntity(
        coordinator, SELECT_DESCRIPTIONS[0], _vehicle(True)
    )
    entity.async_write_ha_state = MagicMock()

    assert entity.current_option == CLIMATE_DURATION_AUTO

    asyncio.run(entity.async_select_option("30"))

    assert coordinator.get_climate_duration_option("v1") == "30"
    assert entity.current_option == "30"
