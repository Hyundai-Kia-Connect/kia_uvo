"""Tests for setting up the climate platform."""

from collections.abc import Iterable

from homeassistant.helpers.entity import Entity
from hyundai_kia_connect_api import Vehicle

from custom_components.kia_uvo import climate
from tests.conftest import make_coordinator, make_hass


async def test_setup_does_not_refresh_the_coordinator_again() -> None:
    """Adding the entity must not fetch all vehicle data a second time.

    ``update_before_add`` runs ``CoordinatorEntity.async_update``, which is
    ``coordinator.async_request_refresh()``, right after the first refresh.
    """
    vehicle = Vehicle(id="v1", name="test", model="test")
    vehicle.air_control_is_on = False
    hass, config_entry = make_hass(make_coordinator(vehicle))
    added: list[tuple[int, bool]] = []

    def add_entities(
        new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        added.append((len(list(new_entities)), update_before_add))

    await climate.async_setup_entry(hass, config_entry, add_entities)

    assert added == [(1, False)]
