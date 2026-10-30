"""Tests for per-vehicle isolation of API failures in the coordinator."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import frame
from homeassistant.helpers.update_coordinator import UpdateFailed
from hyundai_kia_connect_api.exceptions import (
    AuthenticationError,
    RateLimitingError,
    ServiceTemporaryUnavailable,
)
import pytest

from custom_components.kia_uvo import coordinator as coordinator_module
from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator
from custom_components.kia_uvo.entity import HyundaiKiaConnectEntity


class _FakeHass:
    """Minimal hass that runs executor jobs inline and saves tokens."""

    config_entries = MagicMock()

    async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
        return func(*args)


class _FakeVehicle:
    def __init__(self, vehicle_id: str, name: str = "Car") -> None:
        self.id = vehicle_id
        self.name = name


def _make_coordinator(
    vehicles: dict[str, _FakeVehicle],
    failures: dict[str, Exception] | None = None,
    cached_failures: dict[str, Exception] | None = None,
) -> HyundaiKiaConnectDataUpdateCoordinator:
    """Build a coordinator with the attributes the polling code touches."""
    coordinator = HyundaiKiaConnectDataUpdateCoordinator.__new__(
        HyundaiKiaConnectDataUpdateCoordinator
    )
    coordinator.hass = _FakeHass()  # type: ignore[assignment]
    coordinator.force_refresh_interval = 1440
    coordinator._failed_vehicles = set()
    coordinator._vehicle_failures = {}

    failures = failures or {}
    cached_failures = failures if cached_failures is None else cached_failures

    class _FakeManager:
        def __init__(self) -> None:
            self.vehicles = vehicles
            self.failures = failures
            self.cached_failures = cached_failures
            self.calls: list[tuple[str, str]] = []

        def update_vehicle_with_cached_state(self, vehicle_id: str) -> None:
            self.calls.append(("cached", vehicle_id))
            if vehicle_id in self.cached_failures:
                raise self.cached_failures[vehicle_id]

        def check_and_force_update_vehicle(
            self, interval: int, vehicle_id: str
        ) -> None:
            self.calls.append(("force", vehicle_id))
            if vehicle_id in self.failures:
                raise self.failures[vehicle_id]

        def force_refresh_vehicle_state(self, vehicle_id: str) -> None:
            self.calls.append(("force-now", vehicle_id))
            if vehicle_id in self.failures:
                raise self.failures[vehicle_id]

        def check_and_refresh_token(self) -> bool:
            self.token_check = True
            return False

        token = MagicMock()

    coordinator.vehicle_manager = _FakeManager()  # type: ignore[assignment]
    return coordinator


async def test_api_error_marks_only_failing_vehicle() -> None:
    """A 5031 on one vehicle must not touch the other one."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a"), "b": _FakeVehicle("b")},
        {"a": ServiceTemporaryUnavailable("Unavailable remote control")},
    )

    await coordinator._async_poll_vehicles(mode="cached")

    assert coordinator.vehicle_available("a") is False
    assert coordinator.vehicle_available("b") is True
    assert coordinator.vehicle_manager.calls == [("cached", "a"), ("cached", "b")]


async def test_vehicle_error_clears_after_successful_poll() -> None:
    """A recovered vehicle becomes available again without a reload."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a")},
        {"a": ServiceTemporaryUnavailable("boom")},
    )
    await coordinator._async_poll_vehicles(mode="cached")
    assert coordinator.vehicle_available("a") is False

    coordinator.vehicle_manager.failures.pop("a")
    await coordinator._async_poll_vehicles(mode="cached")

    assert coordinator.vehicle_available("a") is True


async def test_rate_limiting_error_raises_update_failed() -> None:
    """Rate limiting is account level and must never be isolated."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a")}, {"a": RateLimitingError("slow down")}
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_poll_vehicles(mode="cached")


async def test_non_api_exception_raises_update_failed() -> None:
    """A network error is account level."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a")}, {"a": TimeoutError("net")}
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_poll_vehicles(mode="cached")


async def test_auth_error_from_one_vehicle_does_not_fail_account() -> None:
    """resCode 7501 is a per-vehicle answer: only that vehicle goes down."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a"), "b": _FakeVehicle("b")},
        {"a": AuthenticationError("7501")},
    )

    await coordinator._async_poll_vehicles(mode="cached")

    assert coordinator.vehicle_available("a") is False
    assert coordinator.vehicle_available("b") is True


async def test_auth_error_from_all_vehicles_raises_config_entry_auth_failed() -> None:
    """When every vehicle fails with an auth error, the account is at fault."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a"), "b": _FakeVehicle("b")},
        {"a": AuthenticationError("7501"), "b": AuthenticationError("7501")},
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_poll_vehicles(mode="cached")


async def test_force_refresh_falls_back_to_cached_for_failing_vehicle() -> None:
    """A failing force refresh retries that vehicle with the cached state."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a"), "b": _FakeVehicle("b")},
        {"a": ServiceTemporaryUnavailable("boom")},
    )

    await coordinator._async_poll_vehicles(mode="check")

    assert coordinator.vehicle_manager.calls == [
        ("force", "a"),
        ("cached", "a"),
        ("force", "b"),
    ]
    assert coordinator.vehicle_available("a") is False
    assert coordinator.vehicle_available("b") is True


async def test_force_refresh_timeout_falls_back_to_cached() -> None:
    """A force refresh that times out still gets the cached state."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a")},
        failures={"a": TimeoutError("car asleep")},
        cached_failures={},
    )

    await coordinator._async_poll_vehicles(mode="check")

    assert coordinator.vehicle_manager.calls == [("force", "a"), ("cached", "a")]
    assert coordinator.vehicle_available("a") is True


async def test_force_mode_uses_the_explicit_force_refresh() -> None:
    """The force_update service must force a fresh read, not a cached one."""
    coordinator = _make_coordinator({"a": _FakeVehicle("a")})

    await coordinator._async_poll_vehicles(mode="force")

    assert coordinator.vehicle_manager.calls == [("force-now", "a")]


async def test_error_state_pruned_for_removed_vehicle() -> None:
    """A vehicle dropped from the account must not keep an error entry."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a")}, {"a": ServiceTemporaryUnavailable("boom")}
    )
    await coordinator._async_poll_vehicles(mode="cached")
    assert coordinator._failed_vehicles == {"a"}

    del coordinator.vehicle_manager.vehicles["a"]
    await coordinator._async_poll_vehicles(mode="cached")

    assert coordinator._failed_vehicles == set()


class _FakeEntity(HyundaiKiaConnectEntity):
    """Minimal entity to exercise the availability override."""


def _make_entity(vehicle: _FakeVehicle, available: bool) -> _FakeEntity:
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.vehicle_available.return_value = available
    entity = _FakeEntity(coordinator, vehicle)
    return entity


def test_entity_unavailable_when_vehicle_failed() -> None:
    """A vehicle that failed its poll takes only its own entities down."""
    entity = _make_entity(_FakeVehicle("a"), available=False)
    assert entity.available is False


def test_entity_available_when_vehicle_is_healthy() -> None:
    """A healthy vehicle stays available even if the account is fine."""
    entity = _make_entity(_FakeVehicle("b"), available=True)
    assert entity.available is True


def test_entity_unavailable_when_account_update_failed() -> None:
    """An account-level failure still takes every entity down."""
    entity = _make_entity(_FakeVehicle("b"), available=True)
    entity.coordinator.last_update_success = False
    assert entity.available is False


async def test_failed_force_refresh_is_logged_when_cached_fallback_works(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed force refresh must stay visible even if the cache answers."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a", name="Sold Car")},
        failures={"a": ServiceTemporaryUnavailable("boom")},
        cached_failures={},
    )

    with caplog.at_level(
        logging.WARNING, logger="custom_components.kia_uvo.coordinator"
    ):
        await coordinator._async_poll_vehicles(mode="check")

    assert any(
        "Sold Car" in record.message and "boom" in record.message
        for record in caplog.records
    )
    # the cached fallback answered, so the vehicle still has data
    assert coordinator.vehicle_available("a") is True


async def test_unexpected_error_is_logged_with_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An account-level failure must be logged with its traceback."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a")}, {"a": TimeoutError("net")}
    )

    with (
        caplog.at_level(logging.ERROR, logger="custom_components.kia_uvo.coordinator"),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_poll_vehicles(mode="cached")

    assert any(record.exc_info is not None for record in caplog.records)


async def test_third_consecutive_failure_logs_actionable_hint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """After three failures the log tells the user how to stop the polling."""
    coordinator = _make_coordinator(
        {"a": _FakeVehicle("a", name="Sold Car")},
        {"a": ServiceTemporaryUnavailable("boom")},
    )

    with caplog.at_level(
        logging.WARNING, logger="custom_components.kia_uvo.coordinator"
    ):
        for _ in range(3):
            await coordinator._async_poll_vehicles(mode="cached")

    assert any(
        "Sold Car" in record.message and "disable its device" in record.message
        for record in caplog.records
    )


_NOON = dt.datetime(2026, 10, 28, 12, 0, 0, tzinfo=dt.UTC)
_LATE = dt.datetime(2026, 10, 28, 23, 0, 0, tzinfo=dt.UTC)


def _make_update_coordinator(
    vehicles: dict[str, _FakeVehicle],
) -> HyundaiKiaConnectDataUpdateCoordinator:
    """Build a coordinator with the attributes the update paths touch."""
    coordinator = _make_coordinator(vehicles)
    coordinator.data = None  # type: ignore[assignment]
    coordinator.scan_interval = 1800
    coordinator.no_force_refresh_hour_start = 22
    coordinator.no_force_refresh_hour_finish = 7
    entry = MagicMock()
    entry.data = {}
    entry.options = {}
    coordinator.config_entry = entry  # type: ignore[assignment]
    return coordinator


async def test_first_update_uses_check_mode_outside_no_force_window() -> None:
    """The periodic poll lets the library pick force or cached, per vehicle."""
    coordinator = _make_update_coordinator({"a": _FakeVehicle("a")})

    with patch.object(coordinator_module.dt_util, "now", return_value=_NOON):
        await coordinator._async_update_data()

    assert coordinator.vehicle_manager.calls == [("force", "a")]


async def test_first_update_polls_cached_during_no_force_window() -> None:
    """Inside the no-force hours the periodic poll uses the cached state."""
    coordinator = _make_update_coordinator({"a": _FakeVehicle("a")})

    with patch.object(coordinator_module.dt_util, "now", return_value=_LATE):
        await coordinator._async_update_data()

    assert coordinator.vehicle_manager.calls == [("cached", "a")]


async def test_update_service_polls_cached() -> None:
    """The update service runs the per-vehicle cached poll for every vehicle."""
    coordinator = _make_update_coordinator(
        {"a": _FakeVehicle("a"), "b": _FakeVehicle("b")}
    )

    with patch.object(
        HyundaiKiaConnectDataUpdateCoordinator, "async_set_updated_data"
    ) as notify:
        await coordinator.async_update_all()

    assert coordinator.vehicle_manager.calls == [("cached", "a"), ("cached", "b")]
    assert notify.call_count == 2 or notify.called
    assert notify.call_count >= 1


async def test_force_update_service_forces_each_vehicle() -> None:
    """The force_update service reads each vehicle fresh, not from the cache."""
    coordinator = _make_update_coordinator(
        {"a": _FakeVehicle("a"), "b": _FakeVehicle("b")}
    )

    with patch.object(
        HyundaiKiaConnectDataUpdateCoordinator, "async_set_updated_data"
    ) as notify:
        await coordinator.async_force_update_all()

    assert coordinator.vehicle_manager.calls == [("force-now", "a"), ("force-now", "b")]
    assert notify.called


def test_init_creates_the_per_vehicle_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh coordinator starts with empty per-vehicle failure state."""
    monkeypatch.setattr(frame, "report_usage", lambda *args, **kwargs: None)
    hass = MagicMock()
    hass.config.language = "en"
    entry = MagicMock()
    entry.data = {"region": 1, "brand": 2, "username": "u", "password": "p", "pin": ""}
    entry.options = {
        "scan_interval": 30,
        "force_refresh": 1440,
        "no_force_refresh_hour_start": 22,
        "no_force_refresh_hour_finish": 7,
        "enable_geolocation_entity": False,
        "use_email_with_geocode_api": False,
    }

    coordinator = HyundaiKiaConnectDataUpdateCoordinator(hass, entry)

    assert coordinator._failed_vehicles == set()
    assert coordinator._vehicle_failures == {}
