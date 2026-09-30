"""Shared pytest configuration for kia_uvo tests."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from hyundai_kia_connect_api import Vehicle

pytest.register_assert_rewrite("custom_components.kia_uvo")

from custom_components.kia_uvo import sensor as sensor_platform
from custom_components.kia_uvo.const import DOMAIN

UNIQUE_ID = "uid"


def make_coordinator(*vehicles: Vehicle) -> MagicMock:
    """A coordinator stub holding ``vehicles``, keyed by ``vehicle.id``.

    Coroutine methods that platform setup awaits are AsyncMocks; add new ones
    here so every test picks them up.
    """
    coordinator = MagicMock()
    coordinator.vehicle_manager.vehicles = {v.id: v for v in vehicles}
    coordinator.async_supports_svm = AsyncMock(return_value=False)
    return coordinator


def make_hass(coordinator: MagicMock) -> tuple[MagicMock, MagicMock]:
    """A ``(hass, config_entry)`` pair wired to ``coordinator``."""
    hass = MagicMock()
    hass.data = {DOMAIN: {UNIQUE_ID: coordinator}}
    config_entry = MagicMock(unique_id=UNIQUE_ID)
    return hass, config_entry


@pytest.fixture
def setup_sensors() -> Callable[..., Awaitable[dict[str, Any]]]:
    """Run the real sensor ``async_setup_entry`` for the given vehicles.

    Returns the created entities that have an ``entity_description``, keyed
    by description key.
    """

    async def _setup(*vehicles: Vehicle) -> dict[str, Any]:
        hass, config_entry = make_hass(make_coordinator(*vehicles))
        created: list[Any] = []
        await sensor_platform.async_setup_entry(hass, config_entry, created.extend)
        return {
            entity.entity_description.key: entity
            for entity in created
            if getattr(entity, "entity_description", None) is not None
        }

    return _setup
