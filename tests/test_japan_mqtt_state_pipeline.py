"""Replay delayed MQTT deltas through the real JP mapper and HA state machine."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import StateMachine
from hyundai_kia_connect_api import Token, Vehicle
from hyundai_kia_connect_api.KiaUvoApiJP import KiaUvoApiJP
from hyundai_kia_connect_api.japan_mqtt import JapanMqttSession
from test_region_operation_serialization import coordinator

from custom_components.kia_uvo.lock import HyundaiKiaConnectLock


async def test_delayed_unlock_survives_later_unrelated_packet_and_reaches_activity():
    api = KiaUvoApiJP(10, 2, "en")
    api.session.request = Mock(
        side_effect=AssertionError("passive processing must not use HTTP")
    )
    vehicle = Vehicle(id="synthetic-car", ccu_ccs2_protocol_support=1)
    api._vehicle_profiles[vehicle.id] = {"option": {"drvSeatLoc": "R"}}
    baseline = {
        "Date": "20261103020000.000",
        "Drivetrain": {"FuelSystem": {"DTE": {"Total": 300, "Unit": 1}}},
        "Cabin": {
            "Door": {
                "Row1": {"Driver": {"Lock": 0}, "Passenger": {"Lock": 0}},
                "Row2": {"Left": {"Lock": 0}, "Right": {"Lock": 0}},
            }
        },
    }
    api._update_vehicle_properties_ccs2(vehicle, baseline)
    assert vehicle.is_locked is True
    helper = JapanMqttSession(
        Token(
            username="synthetic",
            password="synthetic",
            access_token="Bearer synthetic-access",
        ),
        vehicle.id,
        "synthetic-uuid",
        dict,
    )
    helper._topics = ("synthetic/vss", "synthetic/res", "synthetic/connection")
    helper._http_session.request = Mock(side_effect=AssertionError("no broker setup"))
    api._mqtt_sessions[vehicle.id] = (("synthetic-identity",), helper)

    def publish(state):
        helper._on_message(
            None,
            None,
            SimpleNamespace(
                retain=False,
                topic="synthetic/vss",
                payload=json.dumps({"state": {"Vehicle": state}}).encode(),
            ),
        )

    result = coordinator()
    result.vehicle_manager.api = api
    result.vehicle_manager.vehicles = {vehicle.id: vehicle}
    lock = HyundaiKiaConnectLock.__new__(HyundaiKiaConnectLock)
    lock.coordinator = result
    lock.vehicle = vehicle
    bus = Mock()
    states = StateMachine(bus, asyncio.get_running_loop())
    lock.async_write_ha_state = Mock(
        side_effect=lambda: states.async_set("lock.synthetic_car", lock.state)
    )
    result.async_set_updated_data.side_effect = lambda _: (
        lock._handle_coordinator_update()
    )
    lock._handle_coordinator_update()
    bus.reset_mock()
    elapsed = [0.0]
    result._post_command_watch_clock = lambda: elapsed[0]
    injected = False

    async def wait(delay):
        nonlocal injected
        elapsed[0] += delay
        if elapsed[0] >= 20 and not injected:
            injected = True
            # Both arrive before the next HA pass: retaining only the latest
            # packet would lose the earlier unlock delta.
            publish(
                {
                    "Date": "20261103020020.000",
                    "Cabin": {"Door": {"Row1": {"Driver": {"Lock": 1}}}},
                }
            )
            publish(
                {
                    "Date": "20261103020021.000",
                    "Drivetrain": {"FuelSystem": {"DTE": {"Total": 299, "Unit": 1}}},
                }
            )

    result._async_wait_for_post_command_poll = wait

    async def executor(fn, *args):
        return fn(*args)

    result.hass.async_add_executor_job = AsyncMock(side_effect=executor)
    tasks = []

    def schedule(coro, name, **kwargs):
        task = asyncio.create_task(coro, name=name)
        tasks.append(task)
        return task

    result.hass.async_create_background_task = schedule
    result._start_post_command_state_watch(vehicle.id)
    assert vehicle.is_locked is True
    await asyncio.gather(*tasks)
    assert lock.is_locked is False
    assert states.get("lock.synthetic_car").state == "unlocked"
    changes = [
        call
        for call in bus.async_fire_internal.call_args_list
        if call.args[0] == EVENT_STATE_CHANGED
    ]
    assert len(changes) == 1
    assert changes[0].args[1]["old_state"].state == "locked"
    assert changes[0].args[1]["new_state"].state == "unlocked"
    assert helper.diagnostics["pending_state_updates"] == 0
    api.session.request.assert_not_called()
    helper._http_session.request.assert_not_called()
    result.async_check_and_refresh_token.assert_not_awaited()
    result.vehicle_manager.force_refresh_vehicle_state.assert_not_called()
    helper.close()
