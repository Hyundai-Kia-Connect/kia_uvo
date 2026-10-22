"""Tests for the excluded-vehicles option in the options flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry

from custom_components.kia_uvo import config_flow as config_flow_mod
from custom_components.kia_uvo.const import CONF_EXCLUDED_VEHICLES, DOMAIN


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
