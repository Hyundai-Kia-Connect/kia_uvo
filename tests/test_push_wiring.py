"""Tests for the push (MQTT) wiring in kia_uvo."""

import asyncio
import datetime as dt
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from hyundai_kia_connect_api import Token, Vehicle

from custom_components.kia_uvo import binary_sensor as binary_sensor_platform
from custom_components.kia_uvo.coordinator import (
    HyundaiKiaConnectDataUpdateCoordinator,
)

DOMAIN = "kia_uvo"


# ---------------------------------------------------------------------------
# Entity gate: HyundaiKiaMqttConnectedSensor (project style: mock coordinator)
# ---------------------------------------------------------------------------


class TestMqttConnectedSensorGate:
    def _setup(self, mqtt_enabled: bool, push_supported: bool) -> list[Any]:
        coordinator = MagicMock()
        coordinator.is_mqtt_enabled = mqtt_enabled
        # Flag read directly off the api (the removed is_push_supported
        # property must not come back); getattr tolerance is the platform
        # gate's own concern.
        coordinator.vehicle_manager.api.supports_mqtt_push = push_supported
        # connectivity sensor attaches to the first vehicle for device grouping
        first_vehicle = MagicMock()
        first_vehicle.id = "v1"
        coordinator.vehicle_manager.vehicles = {"v1": first_vehicle}
        hass = MagicMock()
        hass.data = {DOMAIN: {"uid": coordinator}}
        config_entry = MagicMock(unique_id="uid")
        created: list[Any] = []

        async def run() -> None:
            await binary_sensor_platform.async_setup_entry(
                hass, config_entry, created.extend
            )

        asyncio.run(run())
        return created

    def test_created_when_enabled_and_supported(self):
        created = self._setup(True, True)
        sensors = [
            e for e in created if type(e).__name__ == "HyundaiKiaMqttConnectedSensor"
        ]
        assert len(sensors) == 1
        assert sensors[0]._attr_translation_key == "mqtt_connected"
        assert sensors[0]._attr_unique_id == f"{DOMAIN}_v1_mqtt_connected"

    def test_not_created_when_push_unsupported(self):
        assert not any(
            type(e).__name__ == "HyundaiKiaMqttConnectedSensor"
            for e in self._setup(True, False)
        )

    def test_not_created_when_disabled(self):
        assert not any(
            type(e).__name__ == "HyundaiKiaMqttConnectedSensor"
            for e in self._setup(False, True)
        )


# ---------------------------------------------------------------------------
# Lifecycle (wiring methods on a shim instance — the CI stack has no HA
# test harness, so DataUpdateCoordinator super().__init__ cannot run)
# ---------------------------------------------------------------------------


class FakePushApi:
    """Push-capable API double (contract shape of the reworked lib)."""

    supports_mqtt_push = True

    def __init__(self):
        self.broker = {"mqtt_host": "broker.example", "mqtt_port": 8883}
        self.reg = {"client_id": "dev-client", "username": None, "password": None}
        self.register_result: dict | None = {}
        self.calls: list[str] = []

    def get_push_broker_info(self, _token):
        self.calls.append("broker")
        return self.broker

    def register_push_client(self, _token):
        self.calls.append("register_client")
        return self.reg

    def register_push_vehicle(self, _token, vehicle):
        self.calls.append("register_vehicle")
        return self.register_result

    def get_push_vehicle_identity(self, _token, vehicle):
        self.calls.append("identity")
        vehicle.mqtt_vehicle_id = "mqtt-v1"
        return {"mqtt_vehicle_id": "mqtt-v1"}

    def get_push_topics(self, _token, vehicle):
        self.calls.append("topics")
        return []

    def parse_push_message(self, topic, payload):  # pragma: no cover
        return None

    def test_token(self, _token):  # ApiImpl base default — token assumed valid
        return True

    def force_refresh_vehicle_state(self, _token, vehicle):
        self.calls.append("force_refresh")


def _shim_coordinator(hass: MagicMock) -> HyundaiKiaConnectDataUpdateCoordinator:
    """Coordinator wiring methods without the HA super().__init__.

    Only the attributes the wiring touches are set: hass, vehicle_manager,
    _mqtt_enabled, _last_force_refresh.
    """
    from hyundai_kia_connect_api import VehicleManager

    coordinator = object.__new__(HyundaiKiaConnectDataUpdateCoordinator)
    coordinator.hass = hass
    coordinator.vehicle_manager = VehicleManager(
        region=1, brand=2, language="en", username="u", password="p", pin="0000"
    )
    coordinator.vehicle_manager.api = FakePushApi()  # type: ignore[assignment]
    vehicle = Vehicle()
    vehicle.id = "v1"
    coordinator.vehicle_manager.vehicles = {"v1": vehicle}
    coordinator._mqtt_enabled = True
    coordinator._last_force_refresh = 0.0
    coordinator.config_entry = MagicMock()
    coordinator.data: dict = {}
    # DataUpdateCoordinator machinery is not set up in the shim — refresh
    # bookkeeping is out of scope here (the wiring under test is the
    # throttle guard + executor call, not the coordinator update itself).
    coordinator.async_set_updated_data = lambda data: None
    return coordinator


def _patch_hass(coordinator) -> tuple[MagicMock, list]:
    """Patch hass methods used by the wiring; return (mock, created tasks)."""
    hass = coordinator.hass
    call_soon = MagicMock()
    hass.loop.call_soon_threadsafe = call_soon
    created: list = []

    def create_task(coro):
        created.append(coro)
        coro.close()
        return MagicMock()

    hass.async_create_task = create_task
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: fn(*a))
    return call_soon, created


class TestStartMqtt:
    def test_starts_and_registers_callbacks(self):
        hass = MagicMock()
        coordinator = _shim_coordinator(hass)
        _patch_hass(coordinator)
        asyncio.run(coordinator.async_start_mqtt("v1"))
        api = coordinator.vehicle_manager.api
        assert api.calls[:4] == [
            "broker",
            "register_client",
            "identity",
            "register_vehicle",
        ]
        assert "topics" not in api.calls  # transport not connected → no subscribe
        cb = coordinator.vehicle_manager._push_status_callback
        assert (
            cb.__func__ is HyundaiKiaConnectDataUpdateCoordinator._mqtt_status_callback
        )
        assert coordinator.vehicle_manager._push_client is not None

    def test_skips_when_disabled(self):
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        coordinator._mqtt_enabled = False
        asyncio.run(coordinator.async_start_mqtt("v1"))
        assert coordinator.vehicle_manager.api.calls == []

    def test_skips_when_unsupported(self):
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        coordinator.vehicle_manager.api.supports_mqtt_push = False
        asyncio.run(coordinator.async_start_mqtt("v1"))
        assert coordinator.vehicle_manager.api.calls == []


class TestStopMqtt:
    def test_unregisters_and_stops(self):
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        asyncio.run(coordinator.async_start_mqtt("v1"))
        asyncio.run(coordinator.async_stop_mqtt())
        assert coordinator.vehicle_manager._push_status_callback is None
        assert coordinator.vehicle_manager._push_client is None


class TestCallbacks:
    def test_status_callback_bridges_to_loop(self):
        coordinator = _shim_coordinator(MagicMock())
        call_soon, _ = _patch_hass(coordinator)
        coordinator._mqtt_status_callback("v1", "Status")
        call_soon.assert_called_with(coordinator._schedule_mqtt_refresh, "v1")

    def test_schedule_refresh_for_known_vehicle_tasks_force_refresh(self):
        coordinator = _shim_coordinator(MagicMock())
        _, created = _patch_hass(coordinator)
        coordinator._schedule_mqtt_refresh("v1")
        assert len(created) == 1
        assert created[0].cr_code.co_name == "async_force_refresh_vehicle"

    def test_schedule_refresh_skips_unknown_vehicle(self):
        coordinator = _shim_coordinator(MagicMock())
        _, created = _patch_hass(coordinator)
        coordinator._schedule_mqtt_refresh("ghost")
        assert created == []

    def test_connection_callback_bridges_to_loop(self):
        coordinator = _shim_coordinator(MagicMock())
        call_soon, _ = _patch_hass(coordinator)
        coordinator._mqtt_connection_callback(True)
        call_soon.assert_called_with(coordinator._schedule_connection_refresh)


class TestForceRefreshThrottle:
    def test_second_call_within_60s_skips_executor(self):
        hass = MagicMock()
        coordinator = _shim_coordinator(hass)
        _, _ = _patch_hass(coordinator)
        # token always valid → check_and_refresh_token skips the API
        coordinator.vehicle_manager.token = Token(valid_until=dt.datetime.max)

        # executor runs check_and_refresh_token BEFORE the refresh itself,
        # so count the actual refresh calls on the API fake instead.
        vm = coordinator.vehicle_manager
        asyncio.run(coordinator.async_force_refresh_vehicle("v1"))
        first_ts = coordinator._last_force_refresh
        assert vm.api.calls.count("force_refresh") == 1

        asyncio.run(coordinator.async_force_refresh_vehicle("v1"))
        assert vm.api.calls.count("force_refresh") == 1  # throttled
        assert coordinator._last_force_refresh == first_ts

        # outside the window the refresh proceeds again
        coordinator._last_force_refresh -= 61.0
        asyncio.run(coordinator.async_force_refresh_vehicle("v1"))
        assert vm.api.calls.count("force_refresh") == 2


@pytest.mark.parametrize("topic_type", ["Status", "Location"])
def test_status_callback_types_bridged(topic_type):
    coordinator = _shim_coordinator(MagicMock())
    call_soon, _ = _patch_hass(coordinator)
    coordinator._mqtt_status_callback("v1", topic_type)
    assert call_soon.call_count == 1
