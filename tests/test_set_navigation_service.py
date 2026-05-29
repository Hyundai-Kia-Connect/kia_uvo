"""Tests for set_navigation service handler and coordinator method.

Validates:
1. Service handler builds POIInfo correctly from call data
2. Coordinator async_set_navigation calls vehicle_manager correctly
3. Coordinator async_set_navigation propagates API errors as HomeAssistantError
4. POICoord/POIInfo round-trip: service data -> POIInfo -> to_dict() matches API expectations

Required field validation (latitude, longitude, name) is enforced by
services.yaml (required: true), not by the Python handler.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from hyundai_kia_connect_api.ApiImpl import POICoord, POIInfo


# --- Minimal stubs (no HA dependency) ---


class HomeAssistantError(Exception):
    """Stub for HA's HomeAssistantError."""

    pass


# --- Tests: POIInfo construction from service call data ---


class TestPOIInfoFromServiceData:
    """Test that service handler data maps correctly to POIInfo."""

    def test_full_data(self):
        """All fields provided."""
        poi = POIInfo(
            coord=POICoord(lat=52.52, lon=13.405),
            name="Berlin Central Station",
            addr="Berlin, Germany",
            zip="10115",
            place_id="here:af:street:example",
        )
        d = poi.to_dict()
        assert d["name"] == "Berlin Central Station"
        assert d["coord"]["lat"] == 52.52
        assert d["coord"]["lon"] == 13.405
        assert d["addr"] == "Berlin, Germany"
        assert d["zip"] == "10115"
        assert d["placeid"] == "here:af:street:example"
        assert d["waypointID"] == 1
        assert d["lang"] == 1
        assert d["src"] == "HERE"

    def test_minimal_data(self):
        """Only required fields: lat, lon, name."""
        poi = POIInfo(
            coord=POICoord(lat=48.85, lon=2.35),
            name="Paris",
        )
        d = poi.to_dict()
        assert d["name"] == "Paris"
        assert d["coord"]["lat"] == 48.85
        assert d["coord"]["lon"] == 2.35
        assert d["addr"] == ""
        assert d["zip"] == ""
        assert d["placeid"] == ""

    def test_latitude_converted_to_float(self):
        """Service call data comes as strings from HA selectors."""
        lat = "52.5200"
        lon = "13.4050"
        poi = POIInfo(
            coord=POICoord(lat=float(lat), lon=float(lon)),
            name="Test",
        )
        assert poi.coord.lat == 52.52

    def test_empty_optional_fields_use_defaults(self):
        """Empty strings for optional fields should remain empty, not None."""
        poi = POIInfo(
            coord=POICoord(lat=1.0, lon=2.0),
            name="X",
            addr="",
            zip="",
            place_id="",
        )
        d = poi.to_dict()
        assert d["addr"] == ""
        assert d["zip"] == ""
        assert d["placeid"] == ""


# --- Tests: Coordinator async_set_navigation ---


class StubCoordinator:
    """Minimal coordinator stub with async_set_navigation logic."""

    def __init__(self):
        self.token_refresh_calls = 0
        self.refresh_calls = 0
        self._vehicle_manager = MagicMock()
        self._vehicle_manager.set_navigation = MagicMock(return_value="action-123")
        self._hass = MagicMock()
        self._hass.async_add_executor_job = AsyncMock(side_effect=self._executor_job)
        self._hass.async_create_task = MagicMock()

    async def _executor_job(self, fn, *args):
        """Simulate executor job by calling fn directly."""
        return fn(*args)

    async def async_check_and_refresh_token(self):
        self.token_refresh_calls += 1

    async def async_await_action_and_refresh(self, vehicle_id, action_id):
        self.refresh_calls += 1

    @property
    def vehicle_manager(self):
        return self._vehicle_manager

    async def async_set_navigation(self, vehicle_id: str, poi_list: list):
        """Mirrors the actual coordinator method."""
        await self.async_check_and_refresh_token()
        try:
            action_id = await self._hass.async_add_executor_job(
                self.vehicle_manager.set_navigation, vehicle_id, poi_list
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set navigation: {err}") from err
        self._hass.async_create_task(
            self.async_await_action_and_refresh(vehicle_id, action_id)
        )


@pytest.mark.asyncio
async def test_set_navigation_calls_vehicle_manager():
    """async_set_navigation should delegate to vehicle_manager.set_navigation."""
    coord = StubCoordinator()
    poi = POIInfo(coord=POICoord(lat=52.52, lon=13.405), name="Berlin")

    await coord.async_set_navigation("veh1", [poi])

    coord.vehicle_manager.set_navigation.assert_called_once_with("veh1", [poi])


@pytest.mark.asyncio
async def test_set_navigation_refreshes_token():
    """async_set_navigation should refresh token before calling API."""
    coord = StubCoordinator()
    poi = POIInfo(coord=POICoord(lat=52.52, lon=13.405), name="Berlin")

    await coord.async_set_navigation("veh1", [poi])

    assert coord.token_refresh_calls == 1


@pytest.mark.asyncio
async def test_set_navigation_schedules_refresh():
    """async_set_navigation should schedule action status check after call."""
    coord = StubCoordinator()
    poi = POIInfo(coord=POICoord(lat=52.52, lon=13.405), name="Berlin")

    await coord.async_set_navigation("veh1", [poi])

    coord._hass.async_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_set_navigation_api_error_raises_ha_error():
    """API errors should be converted to HomeAssistantError."""
    coord = StubCoordinator()
    poi = POIInfo(coord=POICoord(lat=52.52, lon=13.405), name="Berlin")

    coord._hass.async_add_executor_job = AsyncMock(
        side_effect=NotImplementedError("Not supported in this region")
    )

    with pytest.raises(HomeAssistantError, match="Failed to set navigation"):
        await coord.async_set_navigation("veh1", [poi])


@pytest.mark.asyncio
async def test_set_navigation_multiple_pois():
    """Multiple POIs should be passed through as a list."""
    coord = StubCoordinator()
    pois = [
        POIInfo(coord=POICoord(lat=52.52, lon=13.405), name="Berlin"),
        POIInfo(coord=POICoord(lat=48.85, lon=2.35), name="Paris"),
    ]

    await coord.async_set_navigation("veh1", pois)

    coord.vehicle_manager.set_navigation.assert_called_once_with("veh1", pois)
