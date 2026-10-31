"""Tests for syncing HA device enabled state to the library."""

from unittest.mock import MagicMock

from hyundai_kia_connect_api import Vehicle, VehicleManager
import pytest

from custom_components.kia_uvo import coordinator as coordinator_module
from custom_components.kia_uvo.const import DOMAIN
from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator


def _sync(
    monkeypatch: pytest.MonkeyPatch,
    vehicles: list[Vehicle],
    devices: dict[tuple[str, str], MagicMock],
) -> VehicleManager:
    manager = VehicleManager.__new__(VehicleManager)
    manager.vehicles = {v.id: v for v in vehicles}

    def get_device(identifiers: set[tuple[str, str]]) -> MagicMock | None:
        return next((devices[i] for i in identifiers if i in devices), None)

    registry = MagicMock()
    registry.async_get_device.side_effect = get_device
    monkeypatch.setattr(coordinator_module.dr, "async_get", lambda _: registry)

    coordinator = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    coordinator.hass = MagicMock()
    coordinator.vehicle_manager = manager
    coordinator._sync_vehicle_enabled_states()
    return manager


def test_disabled_device_disables_vehicle(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _sync(
        monkeypatch,
        [Vehicle(id="v1"), Vehicle(id="v2")],
        {
            (DOMAIN, "v1"): MagicMock(disabled=True),
            (DOMAIN, "v2"): MagicMock(disabled=False),
        },
    )
    assert manager.vehicles["v1"].enabled is False
    assert manager.vehicles["v2"].enabled is True


def test_reenabled_device_enables_vehicle(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _sync(
        monkeypatch,
        [Vehicle(id="v1", enabled=False)],
        {(DOMAIN, "v1"): MagicMock(disabled=False)},
    )
    assert manager.vehicles["v1"].enabled is True


def test_device_matched_by_vin(monkeypatch: pytest.MonkeyPatch) -> None:
    """A device registered under an old vehicle id still matches by VIN."""
    manager = _sync(
        monkeypatch,
        [Vehicle(id="new-id", VIN="KMH12345678901234")],
        {(DOMAIN, "vin:KMH12345678901234"): MagicMock(disabled=True)},
    )
    assert manager.vehicles["new-id"].enabled is False


def test_vehicle_without_device_stays_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _sync(monkeypatch, [Vehicle(id="v1")], {})
    assert manager.vehicles["v1"].enabled is True
