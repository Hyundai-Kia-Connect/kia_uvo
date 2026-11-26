"""Tests for the push (MQTT) wiring in kia_uvo."""

import asyncio
import datetime as dt
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from hyundai_kia_connect_api import (
    Token,
    Vehicle,
    mqtt_push_session as mqtt_push_session_mod,
)
import pytest

from custom_components.kia_uvo import binary_sensor as binary_sensor_platform
from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator

DOMAIN = "kia_uvo"


# ---------------------------------------------------------------------------
# Entity gate: the push connectivity binary sensor (project style: mock coordinator)
# ---------------------------------------------------------------------------


class TestPushConnectedSensorGate:
    # Option and region gate in the setup loop (coordinator state, like
    # `_geocode_name`); the per-car tri-state gates via the `exists` callback.
    def _setup(
        self, mqtt_enabled: bool, cci_region: bool, mqtt_push: bool | None = None
    ) -> list[Any]:
        coordinator = MagicMock()
        coordinator.is_push_enabled = mqtt_enabled
        coordinator.vehicle_manager.region = 9 if cci_region else 1
        first_vehicle = MagicMock()
        first_vehicle.id = "v1"
        first_vehicle.supports.mqtt_push = mqtt_push
        coordinator.vehicle_manager.vehicles = {"v1": first_vehicle}
        hass = MagicMock()
        hass.data = {DOMAIN: {"uid": coordinator}}
        config_entry = MagicMock(unique_id="uid")
        created: list[Any] = []

        async def run() -> None:
            await binary_sensor_platform.async_setup_entry(
                hass, config_entry, created.extend
            )
            for e in created:
                if e.entity_description.key == "push_connected":
                    assert e.icon == "mdi:cloud-check"

        asyncio.run(run())
        return created

    def _push_sensors(self, created: list[Any]) -> list[Any]:
        return [e for e in created if e.entity_description.key == "push_connected"]

    def test_created_when_enabled_region_cci_and_capability_unknown(self):
        # None attempts (the lib start_push gate), so the sensor is created.
        sensors = self._push_sensors(self._setup(True, True, None))
        assert len(sensors) == 1
        assert sensors[0].entity_description.translation_key == "push_connected"
        assert sensors[0]._attr_unique_id == f"{DOMAIN}_v1_push_connected"

    def test_created_when_capability_true(self):
        assert len(self._push_sensors(self._setup(True, True, True))) == 1

    def test_not_created_when_capability_false(self):
        assert self._push_sensors(self._setup(True, True, False)) == []

    def test_not_created_when_disabled(self):
        assert self._push_sensors(self._setup(False, True, True)) == []

    def test_not_created_when_region_not_cci(self):
        assert self._push_sensors(self._setup(True, False, True)) == []

    def test_is_on_reads_the_transport_through_the_coordinator(self):
        coordinator = MagicMock()
        coordinator.is_push_connected = True
        coordinator.vehicle_manager.region = 9
        coordinator.is_push_enabled = True
        vehicle = MagicMock()
        vehicle.supports.mqtt_push = True
        coordinator.vehicle_manager.vehicles = {"v1": vehicle}
        hass = MagicMock()
        hass.data = {DOMAIN: {"uid": coordinator}}
        created: list[Any] = []

        async def run() -> None:
            await binary_sensor_platform.async_setup_entry(
                hass, MagicMock(unique_id="uid"), created.extend
            )

        asyncio.run(run())
        sensor = self._push_sensors(created)[0]
        sensor.coordinator = coordinator
        assert sensor.is_on is True


# Lifecycle: wiring methods on a shim instance, because the CI stack has
# no HA test harness (DataUpdateCoordinator super().__init__ cannot run).


class NoPushContractApi:
    """API double without the push contract (stubbed NotImplementedError, as the lib base does)."""

    def __init__(self):
        self.calls: list[str] = []

    def get_push_broker_info(self, _token):
        raise NotImplementedError


class FakeTransport:
    """Session-transport double; nothing connects (the lib covers mechanics)."""

    def __init__(self, on_message=None, on_connect=None, on_disconnect=None):
        self.on_message = on_message
        self.connected = False

    @property
    def is_connected(self):
        return self.connected

    def configure(self, **kwargs): ...
    def set_on_connection_change(self, cb): ...
    def connect(self): ...
    def subscribe(self, topics): ...
    def disconnect(self): ...


@pytest.fixture(autouse=True)
def _fake_transport(monkeypatch):
    monkeypatch.setattr(mqtt_push_session_mod, "MqttTransport", FakeTransport)


class FakePushApi:
    """Push-capable API double (the lib's push contract shape)."""

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

    def get_push_credentials(self, _token):
        self.calls.append("creds")
        return ("dev-client", "stripped-token")

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

    def test_token(self, _token):  # ApiImpl base default: token assumed valid
        return True

    def force_refresh_vehicle_state(self, _token, vehicle):
        self.calls.append("force_refresh")


def _shim_coordinator(hass: MagicMock) -> HyundaiKiaConnectDataUpdateCoordinator:
    """Coordinator wiring methods without the HA super().__init__.

    Only the attributes the wiring touches are set: hass, vehicle_manager,
    _push_enabled.
    """
    from hyundai_kia_connect_api import VehicleManager

    coordinator = object.__new__(HyundaiKiaConnectDataUpdateCoordinator)
    coordinator.hass = hass
    coordinator.vehicle_manager = VehicleManager(
        region=1, brand=2, language="en", username="u", password="p", pin="0000"
    )
    # the lib's start path requires a token (Not logged in otherwise)
    coordinator.vehicle_manager.token = Token("u", "p", valid_until=dt.datetime.max)
    coordinator.vehicle_manager.api = FakePushApi()  # type: ignore[assignment]
    vehicle = Vehicle(id="v1")
    coordinator.vehicle_manager.vehicles = {"v1": vehicle}
    coordinator._push_enabled = True
    coordinator.config_entry = MagicMock()
    coordinator.data: dict = {}
    # DataUpdateCoordinator machinery is out of scope for the shim; the
    # wiring under test is the throttle guard + executor call.
    coordinator.async_set_updated_data = lambda data: None
    # device-registry sync is out of scope for the shim: a MagicMock hass
    # would report every device as disabled and skip the force refresh
    coordinator._sync_vehicle_enabled_states = lambda: None
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


class TestStartPush:
    def test_starts_and_registers_callbacks(self):
        hass = MagicMock()
        coordinator = _shim_coordinator(hass)
        _patch_hass(coordinator)
        asyncio.run(coordinator.async_start_push("v1"))
        api = coordinator.vehicle_manager.api
        assert [c for c in api.calls if c != "creds"][:4] == [
            "broker",
            "register_client",
            "identity",
            "register_vehicle",
        ]
        assert "topics" not in api.calls  # transport not connected → no subscribe
        cb = coordinator.vehicle_manager._push_status_callback
        assert (
            cb.__func__ is HyundaiKiaConnectDataUpdateCoordinator._push_status_callback
        )
        assert coordinator.vehicle_manager._push_session._client is not None

    def test_skips_when_disabled(self):
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        coordinator._push_enabled = False
        asyncio.run(coordinator.async_start_push("v1"))
        assert coordinator.vehicle_manager.api.calls == []

    def test_skips_when_unsupported(self):
        # per-car gate: VehicleManager.start_push returns False before any
        # api call
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        coordinator.vehicle_manager.vehicles["v1"].supports.mqtt_push = False
        asyncio.run(coordinator.async_start_push("v1"))
        assert coordinator.vehicle_manager.api.calls == []

    def test_skips_when_contract_absent(self):
        # region API without the push contract raises NotImplementedError;
        # the wiring skips silently (debug) instead of warning
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        coordinator.vehicle_manager.api = NoPushContractApi()
        asyncio.run(coordinator.async_start_push("v1"))
        assert coordinator.vehicle_manager.api.calls == []


class TestConnectionRefresh:
    def test_schedules_a_coordinator_refresh(self):
        """The connection-change bridge lands an async_request_refresh task."""
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        got: list = []
        coordinator.hass.async_create_task = lambda c: got.append(c)
        coordinator._schedule_connection_refresh()
        assert len(got) == 1
        coro = got[0]
        assert coro.cr_frame.f_code.co_name == "async_request_refresh"
        coro.close()


class TestStopPush:
    def test_start_error_is_contained(self):
        """A start failure surfaces as a warning, not an exception."""
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        coordinator.vehicle_manager = MagicMock(
            start_push=MagicMock(side_effect=RuntimeError("boom"))
        )
        asyncio.run(coordinator.async_start_push("v1"))
        coordinator.vehicle_manager.set_push_status_callback.assert_called_with(
            coordinator._push_status_callback
        )

    def test_stop_error_is_contained(self):
        """A stop failure is contained: callbacks detached, no raise."""
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        coordinator.vehicle_manager = MagicMock(
            stop_push=MagicMock(side_effect=RuntimeError("already down"))
        )
        asyncio.run(coordinator.async_stop_push())
        coordinator.vehicle_manager.set_push_status_callback.assert_called_with(None)

    def test_unregisters_and_stops(self):
        coordinator = _shim_coordinator(MagicMock())
        _patch_hass(coordinator)
        asyncio.run(coordinator.async_start_push("v1"))
        asyncio.run(coordinator.async_stop_push())
        assert coordinator.vehicle_manager._push_status_callback is None
        assert coordinator.vehicle_manager._push_session._client is None


class TestCallbacks:
    def test_status_callback_bridges_to_loop(self):
        coordinator = _shim_coordinator(MagicMock())
        call_soon, _ = _patch_hass(coordinator)
        coordinator._push_status_callback("v1", "Status")
        call_soon.assert_called_with(coordinator._schedule_push_refresh, "v1")

    def test_schedule_refresh_for_known_vehicle_tasks_force_refresh(self):
        coordinator = _shim_coordinator(MagicMock())
        _, created = _patch_hass(coordinator)
        coordinator._schedule_push_refresh("v1")
        assert len(created) == 1
        assert created[0].cr_code.co_name == "async_force_refresh_vehicle"

    def test_schedule_refresh_skips_unknown_vehicle(self):
        coordinator = _shim_coordinator(MagicMock())
        _, created = _patch_hass(coordinator)
        coordinator._schedule_push_refresh("ghost")
        assert created == []

    def test_connection_callback_bridges_to_loop(self):
        coordinator = _shim_coordinator(MagicMock())
        call_soon, _ = _patch_hass(coordinator)
        coordinator._push_connection_callback(True)
        call_soon.assert_called_with(coordinator._schedule_connection_refresh)


class TestForceRefreshThrottle:
    """The throttle guards the push path, not the manual refresh."""

    def _coordinator_with_vehicle(self, last_scanned_at):
        hass = MagicMock()
        coordinator = _shim_coordinator(hass)
        _, created = _patch_hass(coordinator)
        coordinator.vehicle_manager.vehicles["v1"].last_scanned_at = last_scanned_at
        return coordinator, created

    def test_push_refresh_runs_from_no_scan(self):
        coordinator, created = self._coordinator_with_vehicle(None)
        coordinator._schedule_push_refresh("v1")
        assert [c.cr_code.co_name for c in created] == ["async_force_refresh_vehicle"]

    def test_push_refresh_throttled_within_60s_of_last_scan(self):
        recent = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=30)
        coordinator, created = self._coordinator_with_vehicle(recent)
        coordinator._schedule_push_refresh("v1")
        assert created == []

    def test_push_refresh_runs_again_after_the_window(self):
        stale = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=61)
        coordinator, created = self._coordinator_with_vehicle(stale)
        coordinator._schedule_push_refresh("v1")
        assert len(created) == 1
        created[0].close()

    def test_manual_refresh_is_not_throttled(self):
        # A recent last_scanned_at does not skip the executor call.
        recent = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=30)
        coordinator, created = self._coordinator_with_vehicle(recent)
        asyncio.run(coordinator.async_force_refresh_vehicle("v1"))
        assert created == []  # manual refresh runs inline, not as a task
        assert coordinator.vehicle_manager.api.calls.count("force_refresh") == 1

    def test_push_refresh_skips_unknown_vehicle(self):
        coordinator, created = self._coordinator_with_vehicle(None)
        coordinator._schedule_push_refresh("ghost")
        assert created == []


@pytest.mark.parametrize("topic_type", ["Status", "Location"])
def test_status_callback_types_bridged(topic_type):
    coordinator = _shim_coordinator(MagicMock())
    call_soon, _ = _patch_hass(coordinator)
    coordinator._push_status_callback("v1", topic_type)
    assert call_soon.call_count == 1
