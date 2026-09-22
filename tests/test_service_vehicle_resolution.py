"""Tests for resolving device-targeted services to an active vehicle."""

from unittest.mock import MagicMock

import pytest
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.exceptions import HomeAssistantError

from custom_components.kia_uvo import services
from custom_components.kia_uvo.const import DOMAIN


def _resolve(
    monkeypatch: pytest.MonkeyPatch,
    identifiers: list[tuple[str, str]],
) -> str:
    coordinator = MagicMock()
    coordinator.vehicle_manager.vehicles = {
        "vehicle-1": MagicMock(),
        "vehicle-2": MagicMock(),
    }
    hass = MagicMock()
    hass.data = {DOMAIN: {"config-entry": coordinator}}

    registry = MagicMock()
    registry.async_get.return_value = MagicMock(identifiers=identifiers)
    monkeypatch.setattr(services.device_registry, "async_get", lambda _: registry)

    call = MagicMock()
    call.data = {ATTR_DEVICE_ID: "device-1"}
    return services._get_vehicle_id_from_device(hass, call)


def test_vehicle_id_resolution_ignores_vin_identifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A VIN identifier must never be sent to a vehicle-manager lookup."""
    assert (
        _resolve(
            monkeypatch,
            [(DOMAIN, "vehicle-1"), (DOMAIN, "vin:KMH12345678901234")],
        )
        == "vehicle-1"
    )


def test_vehicle_id_resolution_ignores_stale_backend_identifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only an identifier present in the current vehicle manager is valid."""
    assert (
        _resolve(
            monkeypatch,
            [
                (DOMAIN, "old-vehicle-id"),
                (DOMAIN, "vin:KMH12345678901234"),
                (DOMAIN, "vehicle-2"),
            ],
        )
        == "vehicle-2"
    )


def test_vehicle_id_resolution_rejects_missing_active_vehicle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An alias without a current manager key must fail clearly."""
    with pytest.raises(HomeAssistantError, match="No active vehicle found"):
        _resolve(monkeypatch, [(DOMAIN, "vin:KMH12345678901234")])
