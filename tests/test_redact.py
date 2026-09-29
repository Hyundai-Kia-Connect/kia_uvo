"""Tests for the diagnostics redaction module.

Two match lists: long specific substrings (`token`, `deviceid`, `latitude`,
...) caught as substrings, and short collision-prone tokens (`vin`, `pin`,
`lat`, `lon`) caught only on exact normalized-key match. The split keeps
state fields like `*_driving_range*` (contains `vin`) and `*_trip_info*`
(contains `pin`) readable while still redacting GPS, tokens, and VIN.
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
    # exact short keys
    assert redact({"lat": 50.0}) == {"lat": REDACTED}
    assert redact({"lon": 19.0}) == {"lon": REDACTED}
    # longitude/latitude substrings catch the long forms
    assert redact({"location_latitude": 50.0}) == {"location_latitude": REDACTED}
    assert redact({"_location_latitude": 50.0}) == {"_location_latitude": REDACTED}
    assert redact({"_location_longitude": 19.0}) == {"_location_longitude": REDACTED}
    assert redact({"gpsLatitude": 50.0}) == {"gpsLatitude": REDACTED}


def test_redacts_reverse_geocode_address() -> None:
    # enable_geolocation_entity reverse-geocodes the car's GPS into a street
    # address — more identifying than lat/lon. Both _geocode_* fields redacted.
    assert redact({"_geocode_address": {"road": "Rydlówka"}}) == {
        "_geocode_address": REDACTED
    }
    assert redact({"_geocode_name": "Baby Booom, Rydlówka, Kraków"}) == {
        "_geocode_name": REDACTED
    }


def test_redacts_credential_keys() -> None:
    assert redact({"pin": "1234"}) == {"pin": REDACTED}
    assert redact({"password": "x"}) == {"password": REDACTED}
    assert redact({"stamp": "x"}) == {"stamp": REDACTED}
    assert redact({"ccsp_stamp": "x"}) == {"ccsp_stamp": REDACTED}
    assert redact({"userId": "x"}) == {"userId": REDACTED}
    assert redact({"account": "x"}) == {"account": REDACTED}
    assert redact({"email": "x@y"}) == {"email": REDACTED}
    assert redact({"secret": "x"}) == {"secret": REDACTED}


def test_redacts_vin_exact_only() -> None:
    # the actual Vehicle field is `VIN` (normalized: vin) -> redacted
    assert redact({"VIN": "WVW123"}) == {"VIN": REDACTED}
    assert redact({"vin": "WVW123"}) == {"vin": REDACTED}


def test_state_fields_with_short_substrings_survive() -> None:
    """Short tokens (vin, pin, lat, lon) are exact-match-only so ordinary
    state fields that merely contain those letters stay readable."""
    assert redact({"_total_driving_range": 500.0}) == {"_total_driving_range": 500.0}
    assert redact({"_ev_driving_range": 300.0}) == {"_ev_driving_range": 300.0}
    assert redact({"_fuel_driving_range": 200.0}) == {"_fuel_driving_range": 200.0}
    assert redact({"_day_trip_info": []}) == {"_day_trip_info": []}
    assert redact({"_month_trip_info": {}}) == {"_month_trip_info": {}}
    # `related`/`plate` contain `lat` letters but are not exact `lat` -> survive
    assert redact({"related": "x"}) == {"related": "x"}
    assert redact({"plate": "KR123"}) == {"plate": "KR123"}


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


def test_scalars_untouched() -> None:
    assert redact("string") == "string"
    assert redact(42) == 42
    assert redact(None) is None
