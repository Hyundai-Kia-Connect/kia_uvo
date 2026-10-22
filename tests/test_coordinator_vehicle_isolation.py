"""Tests for per-vehicle isolation of API failures in the coordinator."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from hyundai_kia_connect_api.exceptions import (
    AuthenticationError,
    RateLimitingError,
    ServiceTemporaryUnavailable,
)

from custom_components.kia_uvo.coordinator import (
    HyundaiKiaConnectDataUpdateCoordinator,
)
from custom_components.kia_uvo.entity import HyundaiKiaConnectEntity


class _FakeHass:
    """Minimal hass that runs executor jobs inline."""

    async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
        return func(*args)


class _FakeVehicle:
    def __init__(self, vehicle_id: str, name: str = "Car") -> None:
        self.id = vehicle_id
        self.name = name
        self.VIN = f"VIN{vehicle_id}"
        self.enabled = True


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
    coordinator._vehicle_errors = {}
    coordinator._vehicle_failures = {}
    coordinator._excluded_vehicles = set()

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

        def disable_vehicle(self, vehicle_id: str) -> None:
            """Mirror the library's per-vehicle enable flag."""

        def enable_vehicle(self, vehicle_id: str) -> None:
            """Mirror the library's per-vehicle enable flag."""

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
    assert coordinator.vehicle_error("a") == (
        "ServiceTemporaryUnavailable: Unavailable remote control"
    )
    assert coordinator.vehicle_error("b") is None
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
    assert coordinator.vehicle_error("a") is None


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
    assert coordinator.vehicle_error("a") is not None

    del coordinator.vehicle_manager.vehicles["a"]
    await coordinator._async_poll_vehicles(mode="cached")

    assert coordinator.vehicle_errors() == {}


async def test_third_consecutive_failure_logs_actionable_hint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """After three failures the log tells the user how to silence the vehicle."""
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
        "Sold Car" in record.message and "excluded_vehicles" in record.message
        for record in caplog.records
    )


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
