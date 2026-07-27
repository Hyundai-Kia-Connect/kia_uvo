"""Tests for the diagnostics platform.

Uses real Vehicle() dataclass instances (asdict requires a real dataclass,
MagicMock is not one) and a mocked coordinator + hass. No HA runtime.
"""

from __future__ import annotations

import asyncio
import datetime
import threading
from unittest.mock import MagicMock

import pytest
from hyundai_kia_connect_api.Token import Token
from hyundai_kia_connect_api.Vehicle import Vehicle

from custom_components.kia_uvo import diagnostics as diagnostics_mod
from custom_components.kia_uvo.const import DOMAIN
from custom_components.kia_uvo.diagnostics import async_get_config_entry_diagnostics
from custom_components.kia_uvo.redact import REDACTED


def _make_coordinator(token: Token | None = None) -> MagicMock:
    vm = MagicMock()
    vm.api = MagicMock()  # type().__name__ -> "MagicMock"
    vm.vehicles = {}
    vm.token = token
    coordinator = MagicMock()
    coordinator.vehicle_manager = vm
    return coordinator


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.unique_id = "test_uid"
    entry.data = {"region": "europe", "brand": "hyundai"}
    entry.options = {
        "scan_interval": 30,
        "force_refresh": 1440,
        "no_force_refresh_hour_start": 22,
        "no_force_refresh_hour_finish": 7,
        "enable_geolocation_entity": False,
        "use_email_with_geocode_api": False,
    }
    return entry


def _make_hass(coordinator: MagicMock) -> MagicMock:
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_uid": coordinator}}

    # Run executor jobs on a real worker thread so the off-event-loop test can
    # assert thread_id differs from the loop thread.
    def _async_add_executor_job(fn, *args):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, lambda: fn(*args))

    hass.async_add_executor_job = MagicMock(side_effect=_async_add_executor_job)
    return hass


@pytest.fixture(autouse=True)
def _stub_integration(monkeypatch) -> None:
    """async_get_integration is imported into diagnostics.py, so patch the
    module-level reference rather than hass.async_get_integration."""

    async def _fake_async_get_integration(_hass, _domain):
        integration = MagicMock()
        integration.version = "3.7.0"
        return integration

    monkeypatch.setattr(
        diagnostics_mod, "async_get_integration", _fake_async_get_integration
    )


@pytest.mark.asyncio
async def test_payload_shape() -> None:
    token = Token()
    token.valid_until = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    token.device_id = "dev123"
    coordinator = _make_coordinator(token=token)
    hass = _make_hass(coordinator)

    payload = await async_get_config_entry_diagnostics(hass, _make_entry())

    assert payload["region"] == "europe"
    assert payload["brand"] == "hyundai"
    assert payload["api_class"] == "MagicMock"
    assert payload["integration_version"] == "3.7.0"
    assert payload["library_version"] is not None
    assert payload["vehicle_count"] == 0
    assert payload["vehicles"] == []
    assert "scan_interval" in payload["config_options"]


@pytest.mark.asyncio
async def test_vehicle_gps_redacted() -> None:
    vehicle = Vehicle()
    vehicle.id = "car1"
    vehicle._location_latitude = 50.06
    vehicle._location_longitude = 19.92
    coordinator = _make_coordinator()
    coordinator.vehicle_manager.vehicles = {"car1": vehicle}
    hass = _make_hass(coordinator)

    payload = await async_get_config_entry_diagnostics(hass, _make_entry())

    car = payload["vehicles"][0]
    assert car["vehicle_id"] == "car1"
    assert car["data"]["_location_latitude"] == REDACTED
    assert car["data"]["_location_longitude"] == REDACTED
    # ordinary state survives
    assert car["data"]["id"] == "car1"


@pytest.mark.asyncio
async def test_token_meta_has_no_secrets() -> None:
    token = Token()
    token.access_token = "secret_access"
    token.refresh_token = "secret_refresh"
    token.pin = "1234"
    token.device_id = "dev123"
    token.valid_until = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    coordinator = _make_coordinator(token=token)
    hass = _make_hass(coordinator)

    payload = await async_get_config_entry_diagnostics(hass, _make_entry())

    token_meta = payload["auth"]
    assert "access_token" not in token_meta
    assert "refresh_token" not in token_meta
    assert "pin" not in token_meta
    assert "device_id" not in token_meta
    assert token_meta["device_present"] is True
    assert "valid_until" in token_meta


@pytest.mark.asyncio
async def test_token_meta_none_returns_empty() -> None:
    coordinator = _make_coordinator(token=None)
    hass = _make_hass(coordinator)

    payload = await async_get_config_entry_diagnostics(hass, _make_entry())

    assert payload["auth"] == {}


@pytest.mark.asyncio
async def test_config_entry_data_excluded() -> None:
    coordinator = _make_coordinator()
    hass = _make_hass(coordinator)

    payload = await async_get_config_entry_diagnostics(hass, _make_entry())

    # entry.data held region/brand only; no credentials leak at top level
    assert "username" not in payload
    assert "password" not in payload
    assert "pin" not in payload
    assert "auth" in payload  # curated auth metadata dict, not the raw Token


@pytest.mark.asyncio
async def test_config_options_not_redacted() -> None:
    """Option keys like `use_email_with_geocode_api` contain the `email`
    substring; whole-payload redaction would scrub a boolean flag. Only the
    uncontrolled Vehicle data is redacted — constructed top-level fields
    are left intact.
    """
    coordinator = _make_coordinator()
    hass = _make_hass(coordinator)

    payload = await async_get_config_entry_diagnostics(hass, _make_entry())

    opts = payload["config_options"]
    assert opts["use_email_with_geocode_api"] is False
    assert opts["enable_geolocation_entity"] is False
    assert opts["scan_interval"] == 30
    assert REDACTED not in str(opts)


@pytest.mark.asyncio
async def test_library_version_read_off_event_loop(monkeypatch) -> None:
    coordinator = _make_coordinator()
    hass = _make_hass(coordinator)
    loop_thread_id = threading.get_ident()
    seen: dict[str, int] = {}
    real_pkg_version = diagnostics_mod.pkg_version

    def _spy(name: str) -> str:
        seen["thread_id"] = threading.get_ident()
        return real_pkg_version(name)

    monkeypatch.setattr(diagnostics_mod, "pkg_version", _spy)

    payload = await async_get_config_entry_diagnostics(hass, _make_entry())

    assert payload["library_version"] is not None
    assert seen["thread_id"] != loop_thread_id


@pytest.mark.asyncio
async def test_broken_vehicle_does_not_kill_dump() -> None:
    # A non-dataclass instance raises in asdict (dataclasses.asdict requires a
    # dataclass); the dump isolates the failure to that one vehicle.
    class NotADataclass:
        pass

    good = Vehicle()
    good.id = "good"
    coordinator = _make_coordinator()
    coordinator.vehicle_manager.vehicles = {"good": good, "bad": NotADataclass()}
    hass = _make_hass(coordinator)

    payload = await async_get_config_entry_diagnostics(hass, _make_entry())

    vehicles = {v["vehicle_id"]: v for v in payload["vehicles"]}
    assert vehicles["good"]["data"]["id"] == "good"
    assert "error" in vehicles["bad"]
    assert "data" not in vehicles["bad"]
