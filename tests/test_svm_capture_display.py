"""Completed camera captures remain visible when GPS time is omitted."""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from test_region_operation_serialization import coordinator

from custom_components.kia_uvo import coordinator as module
from custom_components.kia_uvo.image import SVMImageEntity
from custom_components.kia_uvo.sensor import SVMStatusSensor


async def test_capture_without_gps_time_updates_status_and_render_cache(monkeypatch):
    result = coordinator()
    result._svm_dewarp = {}
    details = SimpleNamespace(
        captured_at=None, image_bytes=b"synthetic", image_sizes=(5, 1, 1, 1, 1, 1)
    )
    result.hass.async_add_executor_job.return_value = details
    receipt = dt.datetime(2026, 10, 15, tzinfo=dt.UTC)
    monkeypatch.setattr(module.dt_util, "utcnow", lambda: receipt)
    await result.async_request_svm_capture("synthetic")
    assert result.get_svm_image_updated_at("synthetic") == receipt
    assert result.get_cached_svm_details("synthetic").captured_at is None
    sensor = SVMStatusSensor.__new__(SVMStatusSensor)
    sensor.coordinator = result
    sensor.vehicle = SimpleNamespace(id="synthetic")
    assert sensor.available
    assert sensor.native_value == receipt
    details.heading = details.speed = details.door_open = details.trunk_open = None
    assert sensor.extra_state_attributes["timestamp_source"] == "received"
    assert sensor.extra_state_attributes["vehicle_captured_at"] is None
    image = SVMImageEntity.__new__(SVMImageEntity)
    image.coordinator = result
    image.vehicle = sensor.vehicle
    image.async_write_ha_state = MagicMock()
    image._handle_coordinator_update()
    assert image.image_last_updated == receipt
    result.hass.async_add_executor_job = AsyncMock(return_value={"front": b"first"})
    assert await result.async_get_svm_views("synthetic") == {"front": b"first"}
    assert await result.async_get_svm_views("synthetic") == {"front": b"first"}
    result.hass.async_add_executor_job.assert_awaited_once()
    result._cache_svm_details("synthetic", details)
    result.hass.async_add_executor_job.return_value = {"front": b"second"}
    assert await result.async_get_svm_views("synthetic") == {"front": b"second"}


def test_capture_timestamp_is_preserved_when_available():
    result = coordinator()
    captured = dt.datetime(2026, 10, 14, tzinfo=dt.UTC)
    result._cache_svm_details("synthetic", SimpleNamespace(captured_at=captured))
    assert result.get_svm_image_updated_at("synthetic") == captured
    assert result.get_svm_image_updated_at("missing") is None
