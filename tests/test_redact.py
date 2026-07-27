"""Tests for the diagnostics redaction module.

Substring matching errs on the side of over-redaction: a field like
`related` or `plate` will be redacted because it contains `lat`. That is an
accepted, asserted cost — leaking GPS or tokens in a public diagnostics
download is worse than redacting too much.
"""

from custom_components.kia_uvo.redact import REDACTED, redact


def test_redacts_token_keys() -> None:
    assert redact({"access_token": "x"}) == {"access_token": REDACTED}
    assert redact({"refresh_token": "x"}) == {"refresh_token": REDACTED}
    assert redact({"control_token": "x"}) == {"control_token": REDACTED}
    assert redact({"id_token": "x"}) == {"id_token": REDACTED}


def test_redacts_device_id_keys() -> None:
    assert redact({"device_id": "x"}) == {"device_id": REDACTED}
    assert redact({"deviceid": "x"}) == {"deviceid": REDACTED}
    assert redact({"client_device_id": "x"}) == {"client_device_id": REDACTED}


def test_redacts_gps_keys() -> None:
    assert redact({"lat": 50.0}) == {"lat": REDACTED}
    assert redact({"lon": 19.0}) == {"lon": REDACTED}
    assert redact({"location_latitude": 50.0}) == {"location_latitude": REDACTED}
    assert redact({"_location_latitude": 50.0}) == {"_location_latitude": REDACTED}
    assert redact({"gpsLatitude": 50.0}) == {"gpsLatitude": REDACTED}


def test_redacts_credential_keys() -> None:
    assert redact({"pin": "1234"}) == {"pin": REDACTED}
    assert redact({"password": "x"}) == {"password": REDACTED}
    assert redact({"stamp": "x"}) == {"stamp": REDACTED}
    assert redact({"ccsp_stamp": "x"}) == {"ccsp_stamp": REDACTED}
    assert redact({"vin": "WVW123"}) == {"vin": REDACTED}
    assert redact({"userId": "x"}) == {"userId": REDACTED}
    assert redact({"account": "x"}) == {"account": REDACTED}
    assert redact({"email": "x@y"}) == {"email": REDACTED}
    assert redact({"secret": "x"}) == {"secret": REDACTED}


def test_preserves_state_keys() -> None:
    assert redact({"vehicle_id": "abc"}) == {"vehicle_id": "abc"}
    assert redact({"battery_level": 80}) == {"battery_level": 80}
    assert redact({"odometer": 5000}) == {"odometer": 5000}
    assert redact({"region": "europe"}) == {"region": "europe"}
    assert redact({"api_class": "HyundaiCciApiEU"}) == {"api_class": "HyundaiCciApiEU"}


def test_recurses_through_nested_dict() -> None:
    nested = {"vehicles": [{"data": {"_location_latitude": 50.0}}]}
    assert redact(nested) == {"vehicles": [{"data": {"_location_latitude": REDACTED}}]}


def test_recurses_through_list() -> None:
    assert redact([{"lat": 1.0}, {"lon": 2.0}]) == [
        {"lat": REDACTED},
        {"lon": REDACTED},
    ]


def test_over_redaction_is_documented_contract() -> None:
    """`lat` substring matches neutral fields. Accepted: safer than leaking GPS."""
    assert redact({"related": "x"}) == {"related": REDACTED}
    assert redact({"plate": "KR123"}) == {"plate": REDACTED}


def test_scalars_untouched() -> None:
    assert redact("string") == "string"
    assert redact(42) == 42
    assert redact(None) is None
