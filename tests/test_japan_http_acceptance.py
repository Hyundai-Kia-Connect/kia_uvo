"""Replay Japan HTTP acceptance through HA without any MQTT result packets."""

import json
import time
from unittest.mock import Mock

from homeassistant.exceptions import HomeAssistantError
from hyundai_kia_connect_api import Token, Vehicle, VehicleManager
from hyundai_kia_connect_api.const import ORDER_STATUS
from hyundai_kia_connect_api.KiaUvoApiJP import KiaUvoApiJP
import pytest
import requests
from test_region_operation_serialization import coordinator


def pipeline(body=None, failure=None):
    api = KiaUvoApiJP(10, 2, "en")
    helper = Mock()
    helper.request_context = {
        "clientId": "synthetic-client",
        "vehicleId": "synthetic-broker",
    }
    helper.status.side_effect = AssertionError(
        "ordinary controls must not wait for MQTT"
    )
    helper.track.side_effect = AssertionError(
        "ordinary controls must not track MQTT result"
    )
    api._mqtt_for_vehicle = Mock(return_value=helper)
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(
        body
        if body is not None
        else {
            "retCode": "S",
            "resCode": "0000",
            "msgId": "synthetic-action",
        }
    ).encode()
    api.session.request = Mock(side_effect=failure, return_value=response)
    manager = VehicleManager.__new__(VehicleManager)
    manager.api = api
    manager.token = Token(
        username="synthetic",
        password="synthetic",
        access_token="Bearer synthetic-access",
        device_id="synthetic-device",
        pin="synthetic-pin",
        mqtt_registration_uuid="synthetic-uuid",
        control_token="Bearer synthetic-control",
        control_token_expiry=time.time() + 3600,
    )
    vehicle = Vehicle(id="synthetic-car", ccu_ccs2_protocol_support=1, is_locked=True)
    manager.vehicles = {vehicle.id: vehicle}
    manager.update_all_vehicles_with_cached_state = Mock()
    result = coordinator()
    result.vehicle_manager = manager
    result._start_post_command_state_watch = Mock()

    async def executor(fn, *args):
        return fn(*args)

    result.hass.async_add_executor_job = executor
    return result, api, manager, helper, vehicle


@pytest.mark.parametrize(
    "action,command",
    [
        ("async_unlock_vehicle", "open"),
        ("async_stop_climate", "stop"),
    ],
)
async def test_service_result_accepted_with_no_mqtt_reply(action, command):
    result, api, manager, helper, vehicle = pipeline()
    await getattr(result, action)(vehicle.id)
    request = api.session.request.call_args
    assert request.kwargs["json"] == {"command": command}
    assert request.kwargs["timeout"] == (10, 140)
    assert api.session.request.call_count == 1
    helper.status.assert_not_called()
    helper.track.assert_not_called()
    receipt = next(iter(api._japan_actions))
    assert manager.check_action_status(vehicle.id, receipt) == ORDER_STATUS.ACCEPTED
    assert (
        vehicle.is_locked is True
    )  # HTTP acceptance never fabricates a sensor change.
    manager.update_all_vehicles_with_cached_state.assert_called_once()
    result._start_post_command_state_watch.assert_called_once_with(vehicle.id)
    result.async_set_updated_data.assert_called_once()
    assert not result._action_lock.locked()


async def test_service_result_does_not_require_mqtt_correlation_id():
    result, api, manager, helper, vehicle = pipeline(
        {"retCode": "S", "resCode": "0000"}
    )
    await result.async_unlock_vehicle(vehicle.id)
    receipt = next(iter(api._japan_actions))
    assert manager.check_action_status(vehicle.id, receipt) == ORDER_STATUS.ACCEPTED
    helper.status.assert_not_called()
    assert api.session.request.call_count == 1


async def test_accepted_command_still_watches_when_initial_cached_read_fails():
    result, api, manager, _helper, vehicle = pipeline()
    manager.update_all_vehicles_with_cached_state.side_effect = RuntimeError(
        "synthetic cached read failure"
    )
    with pytest.raises(HomeAssistantError, match="service accepted the request"):
        await result.async_unlock_vehicle(vehicle.id)
    result._start_post_command_state_watch.assert_called_once_with(vehicle.id)
    assert api.session.request.call_count == 1
    assert vehicle.is_locked is True
    assert not result._action_lock.locked()


async def test_http_timeout_is_unknown_and_does_not_resend():
    result, api, _manager, helper, vehicle = pipeline(
        failure=requests.Timeout("synthetic")
    )
    with pytest.raises(HomeAssistantError, match="vehicle execution is unknown"):
        await result.async_unlock_vehicle(vehicle.id)
    assert api.session.request.call_count == 1
    assert not getattr(api, "_japan_actions", {})
    helper.status.assert_not_called()
    result._start_post_command_state_watch.assert_not_called()
    assert not result._action_lock.locked()


async def test_vendor_error_is_not_accepted_or_retried():
    result, api, _manager, helper, vehicle = pipeline(
        {"retCode": "F", "resCode": "4002"}
    )
    with pytest.raises(HomeAssistantError, match="invalid request"):
        await result.async_unlock_vehicle(vehicle.id)
    assert api.session.request.call_count == 1
    assert not getattr(api, "_japan_actions", {})
    helper.status.assert_not_called()
    result._start_post_command_state_watch.assert_not_called()
    assert not result._action_lock.locked()
