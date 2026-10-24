"""Tests for the excluded-vehicles option in the options flow."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError

from custom_components.kia_uvo import config_flow as config_flow_mod
from custom_components.kia_uvo.const import CONF_EXCLUDED_VEHICLES, DOMAIN
from custom_components.kia_uvo.coordinator import (
    HyundaiKiaConnectDataUpdateCoordinator,
)


class _FakeVehicle:
    def __init__(self, vehicle_id: str, name: str, vin: str | None) -> None:
        self.id = vehicle_id
        self.name = name
        self.VIN = vin


def _make_entry(
    options: dict[str, Any] | None = None,
) -> ConfigEntry:
    entry = MagicMock(spec=ConfigEntry)
    entry.unique_id = "unique-1"
    entry.options = {CONF_EXCLUDED_VEHICLES: ["VINabc"]} if options is None else options
    return entry


def _make_hass(vehicles: dict[str, _FakeVehicle] | None) -> Any:
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.vehicle_manager.vehicles = vehicles or {}
    hass.data = {DOMAIN: {"unique-1": coordinator}}
    hass.config_entries.async_get_known_entry.return_value = _make_entry()
    return hass


def test_options_offer_the_account_vehicles() -> None:
    """Every vehicle on the account must be selectable for exclusion."""
    hass = _make_hass(
        {
            "v1": _FakeVehicle("v1", "Ioniq 5", "VINabc"),
            "v2": _FakeVehicle("v2", "EV6", "VINdef"),
        }
    )

    options = config_flow_mod._excluded_vehicle_options(hass, _make_entry())

    assert [option["value"] for option in options] == ["VINabc", "VINdef"]
    assert "Ioniq 5" in options[0]["label"]
    assert "VINabc" in options[0]["label"]


def test_options_fall_back_to_vehicle_id_without_vin() -> None:
    """A vehicle without a VIN is selectable by its internal id."""
    hass = _make_hass({"v2": _FakeVehicle("v2", "EV6", None)})

    options = config_flow_mod._excluded_vehicle_options(hass, _make_entry(options={}))

    assert [option["value"] for option in options] == ["v2"]


def test_saved_exclusions_survive_a_not_loaded_entry() -> None:
    """Without a loaded entry the saved exclusions must stay selectable."""
    hass = MagicMock()
    hass.data = {}

    options = config_flow_mod._excluded_vehicle_options(hass, _make_entry())

    assert [option["value"] for option in options] == ["VINabc"]


def test_schema_contains_the_excluded_vehicles_field() -> None:
    """The options form must carry the new multi-select."""
    hass = _make_hass({"v1": _FakeVehicle("v1", "Ioniq 5", "VINabc")})
    handler = config_flow_mod.HyundaiKiaConnectOptionFlowHandler()
    handler.hass = hass
    handler.handler = "entry-1"

    schema = handler._build_options_schema()

    assert CONF_EXCLUDED_VEHICLES in {str(key) for key in schema.schema}


class _FakeHass:
    """Minimal hass that runs executor jobs inline."""

    async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
        return func(*args)


class _FakeManager:
    """Library stand-in recording every vehicle interaction."""

    def __init__(self, vehicles: dict[str, _FakeVehicle]) -> None:
        self.vehicles = vehicles
        self.calls: list[tuple[str, str]] = []
        self.disabled: list[str] = []
        self.enabled: list[str] = []

    def update_vehicle_with_cached_state(self, vehicle_id: str) -> None:
        self.calls.append(("cached", vehicle_id))

    def check_and_force_update_vehicle(self, interval: int, vehicle_id: str) -> None:
        self.calls.append(("force", vehicle_id))

    def force_refresh_vehicle_state(self, vehicle_id: str) -> None:
        self.calls.append(("force-now", vehicle_id))

    def disable_vehicle(self, vehicle_id: str) -> None:
        self.disabled.append(vehicle_id)

    def enable_vehicle(self, vehicle_id: str) -> None:
        self.enabled.append(vehicle_id)


def _make_polling_coordinator(
    vehicles: dict[str, _FakeVehicle],
    excluded: set[str],
) -> HyundaiKiaConnectDataUpdateCoordinator:
    """Build a coordinator with the attributes the exclusion code touches."""
    coordinator = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    coordinator.hass = _FakeHass()  # type: ignore[assignment]
    coordinator.force_refresh_interval = 1440
    coordinator._vehicle_errors = {}
    coordinator._vehicle_failures = {}
    coordinator._excluded_vehicles = set(excluded)
    coordinator._action_lock = asyncio.Lock()
    coordinator.vehicle_manager = _FakeManager(vehicles)  # type: ignore[assignment]
    return coordinator


async def test_excluded_vehicle_is_never_polled() -> None:
    """An excluded vehicle must not be called at all."""
    coordinator = _make_polling_coordinator(
        {
            "a": _FakeVehicle("a", "Ioniq 5", "VINa"),
            "b": _FakeVehicle("b", "EV6", "VINb"),
        },
        excluded={"VINb"},
    )

    await coordinator._async_poll_vehicles(mode="cached")

    assert coordinator.vehicle_manager.calls == [("cached", "a")]


async def test_exclusions_are_applied_to_the_library_on_every_cycle() -> None:
    """The library's enabled flag is refreshed every cycle, not only at setup."""
    coordinator = _make_polling_coordinator(
        {
            "a": _FakeVehicle("a", "Ioniq 5", "VINa"),
            "b": _FakeVehicle("b", "EV6", "VINb"),
        },
        excluded={"VINb"},
    )

    await coordinator._async_poll_vehicles(mode="cached")
    await coordinator._async_poll_vehicles(mode="cached")

    assert coordinator.vehicle_manager.disabled == ["b", "b"]
    assert coordinator.vehicle_manager.enabled == ["a", "a"]


async def test_action_on_excluded_vehicle_is_refused() -> None:
    """A command for an excluded vehicle must fail with a clear message."""
    coordinator = _make_polling_coordinator(
        {"b": _FakeVehicle("b", "EV6", "VINb")}, excluded={"VINb"}
    )

    with pytest.raises(HomeAssistantError, match="excluded from polling"):
        await coordinator.async_lock_vehicle("b")
