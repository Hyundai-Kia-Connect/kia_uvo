"""Redact credentials, GPS, and identity data from a diagnostics dump before
it leaves the user's Home Assistant instance.

Vehicle state mixes ordinary data with genuinely sensitive values: access and
refresh tokens, device id, PIN, GPS coordinates, VIN, account/email. Region
subclasses add fields with unpredictable names (`gpsLatitude` vs
`_location_latitude` vs `lat`). Rather than enumerate every known sensitive
key, this walks the whole dump and redacts any value whose key contains a
sensitive substring — erring on catching the field by name. Over-redaction
(redacting a neutral field like `related` or `plate`) is the accepted cost;
leaking GPS or a token in a public issue attachment is not.
"""

from __future__ import annotations

from typing import Any

REDACTED = "**REDACTED**"

_SENSITIVE_SUBSTRINGS = (
    "token",
    "deviceid",
    "lat",
    "lon",
    "pin",
    "password",
    "stamp",
    "cookie",
    "account",
    "email",
    "vin",
    "userid",
    "sessionid",
    "rmtoken",
    "secret",
)


def _is_sensitive_key(key: str) -> bool:
    # Strip underscores/hyphens so `device_id` matches the `deviceid` substring
    # (and `client_device_id` -> `clientdeviceid`). Region subclasses spell the
    # same concept with and without separators.
    normalized = key.lower().replace("_", "").replace("-", "")
    return any(s in normalized for s in _SENSITIVE_SUBSTRINGS)


def redact(obj: Any) -> Any:
    """Recursively redact dict values whose key matches a sensitive substring."""
    if isinstance(obj, dict):
        return {
            key: (REDACTED if _is_sensitive_key(key) else redact(value))
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    return obj
