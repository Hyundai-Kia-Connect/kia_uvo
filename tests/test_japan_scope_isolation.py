"""Japan setup and camera extensions must not change other regional entries."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components import kia_uvo
from custom_components.kia_uvo.image import SVMImageEntity
from custom_components.kia_uvo.sensor import SVMStatusSensor


@pytest.mark.parametrize("region,japan", [(10, True), (1, False), (3, False)])
async def test_only_japan_selects_the_japan_coordinator(monkeypatch, region, japan):
    def factory():
        result = MagicMock()
        result.async_config_entry_first_refresh = AsyncMock()
        return MagicMock(return_value=result)

    base = factory()
    jp = factory()
    monkeypatch.setattr(kia_uvo, "HyundaiKiaConnectDataUpdateCoordinator", base)
    monkeypatch.setattr(kia_uvo, "JapanDataUpdateCoordinator", jp)
    monkeypatch.setattr(kia_uvo, "async_setup_services", MagicMock())
    hass = SimpleNamespace(
        data={}, config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock())
    )
    entry = SimpleNamespace(data={"region": region}, unique_id="synthetic")
    assert await kia_uvo.async_setup_entry(hass, entry)
    selected, other = (jp, base) if japan else (base, jp)
    selected.assert_called_once_with(hass, entry)
    other.assert_not_called()


def test_non_japan_camera_missing_timestamp_keeps_original_behavior():
    coordinator = MagicMock()
    details = SimpleNamespace(
        captured_at=None, heading=None, speed=None, door_open=None, trunk_open=None
    )
    coordinator.get_cached_svm_details.return_value = details
    coordinator.get_svm_image_updated_at.return_value = "should not be used"
    image = SVMImageEntity.__new__(SVMImageEntity)
    image.coordinator = coordinator
    image.vehicle = SimpleNamespace(id="synthetic")
    image.async_write_ha_state = MagicMock()
    image._handle_coordinator_update()
    assert image.image_last_updated is None
    coordinator.get_svm_image_updated_at.assert_not_called()
    status = SVMStatusSensor.__new__(SVMStatusSensor)
    status.coordinator = coordinator
    status.vehicle = image.vehicle
    assert status.native_value is None
    assert "timestamp_source" not in status.extra_state_attributes
    assert "vehicle_captured_at" not in status.extra_state_attributes
