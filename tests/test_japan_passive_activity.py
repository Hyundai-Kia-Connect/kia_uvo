"""Only observed vehicle changes produce lock activity, not service acceptance."""

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, Mock

from homeassistant.const import (
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    EVENT_STATE_REPORTED,
)
from homeassistant.core import StateMachine
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import ORDER_STATUS
from test_region_operation_serialization import coordinator

from custom_components.kia_uvo.lock import HyundaiKiaConnectLock


async def test_delayed_passive_state_reaches_lock_and_ha_activity_event():
    result = coordinator()
    vehicle = Vehicle(id="synthetic-car", is_locked=True)
    vehicle.last_updated_at = dt.datetime(2026, 11, 3, tzinfo=dt.UTC)
    result.vehicle_manager.vehicles = {vehicle.id: vehicle}
    lock = HyundaiKiaConnectLock.__new__(HyundaiKiaConnectLock)
    lock.coordinator = result
    lock.vehicle = vehicle

    # Use HA's real state transition handling without starting recorder or services.
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

    latest_locked = [True]

    def read_cached_state():
        vehicle.is_locked = latest_locked[0]
        if not latest_locked[0]:
            vehicle.last_updated_at = dt.datetime(2026, 11, 3, 0, 0, 20, tzinfo=dt.UTC)

    result.vehicle_manager.update_all_vehicles_with_cached_state.side_effect = (
        read_cached_state
    )

    async def executor(fn, *args):
        return fn(*args)

    result.hass.async_add_executor_job = AsyncMock(side_effect=executor)
    await result._async_refresh_command_state(ORDER_STATUS.ACCEPTED)
    assert lock.is_locked is True
    assert states.get("lock.synthetic_car").state == "locked"
    assert [call.args[0] for call in bus.async_fire_internal.call_args_list] == [
        EVENT_STATE_REPORTED
    ]

    # The delayed response represents new cached telemetry, not a second command.
    latest_locked[0] = False
    bus.reset_mock()
    await result._async_refresh_command_state(ORDER_STATUS.ACCEPTED)
    assert lock.is_locked is False
    event = bus.async_fire_internal.call_args
    assert event.args[0] == EVENT_STATE_CHANGED
    assert event.args[1]["old_state"].state == "locked"
    assert event.args[1]["new_state"].state == "unlocked"
    assert EVENT_LOGBOOK_ENTRY not in [
        call.args[0] for call in bus.async_fire_internal.call_args_list
    ]
    result.vehicle_manager.unlock.assert_not_called()
    result.vehicle_manager.force_refresh_vehicle_state.assert_not_called()
    assert result.vehicle_manager.update_all_vehicles_with_cached_state.call_count == 2


async def test_passive_watcher_observes_late_unlock_after_unrelated_update():
    result = coordinator()
    vehicle = Vehicle(id="synthetic-car", is_locked=True)
    baseline = dt.datetime(2026, 11, 3, tzinfo=dt.UTC)
    vehicle.last_updated_at = baseline
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
    received = []
    result._post_command_watch_clock = lambda: elapsed[0]

    async def wait_for_poll(delay):
        elapsed[0] += delay

    result._async_wait_for_post_command_poll = wait_for_poll

    def apply_cached_telemetry(target):
        assert target is vehicle
        if elapsed[0] >= 20 and "unlock" not in received:
            received.append("unlock")
            target.is_locked = False
            target.last_updated_at = baseline + dt.timedelta(seconds=20)
            return True
        if elapsed[0] >= 6 and "unrelated" not in received:
            received.append("unrelated")
            target.last_updated_at = baseline + dt.timedelta(seconds=6)
            return True
        return False

    result.vehicle_manager.api.apply_cached_mqtt_state = Mock(
        side_effect=apply_cached_telemetry
    )

    async def executor(fn, *args):
        return fn(*args)

    result.hass.async_add_executor_job = AsyncMock(side_effect=executor)
    tasks = []

    def schedule(coro, name, *, eager_start=False):
        task = asyncio.create_task(coro, name=name)
        tasks.append(task)
        return task

    result.hass.async_create_background_task = schedule
    result._start_post_command_state_watch(vehicle.id)
    assert vehicle.is_locked is True
    assert states.get("lock.synthetic_car").state == "locked"
    await asyncio.gather(*tasks)
    assert received == ["unrelated", "unlock"]
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
    assert EVENT_LOGBOOK_ENTRY not in [
        call.args[0] for call in bus.async_fire_internal.call_args_list
    ]
    result.async_check_and_refresh_token.assert_not_awaited()
    result.vehicle_manager.unlock.assert_not_called()
    result.vehicle_manager.force_refresh_vehicle_state.assert_not_called()
    result.vehicle_manager.update_all_vehicles_with_cached_state.assert_not_called()
    assert elapsed[0] >= result._POST_COMMAND_WATCH_SECONDS
