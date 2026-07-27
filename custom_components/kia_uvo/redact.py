"""Redact credentials, GPS, and identity data from a diagnostics dump.

Walks the dump and redacts any value whose key matches a sensitive pattern.
Two lists: `_SENSITIVE_SUBSTRINGS` (long, specific: `token`, `deviceid`,
`latitude`, ...) matched as substrings, and `_SENSITIVE_EXACT` (short,
collision-prone: `vin`, `pin`, `lat`, `lon`) matched only on exact
normalized key. `vin`/`pin` as substrings would redact every
`*_driving_range*` (`driving` contains `vin`) and `*_trip_info*` field
(`tripinfo` contains `pin`). Keys are normalized (underscores/hyphens
stripped, lowercased) so `device_id` matches the `deviceid` substring.
"""

from __future__ import annotations

from typing import Any

REDACTED = "**REDACTED**"

_SENSITIVE_SUBSTRINGS = (
    "token",
    "deviceid",
    "password",
    "stamp",
    "cookie",
    "account",
    "email",
    "userid",
    "sessionid",
    "rmtoken",
    "secret",
    "latitude",
    "longitude",
    "geocode",
)

_SENSITIVE_EXACT = frozenset(
    {
        "vin",
        "pin",
        "lat",
        "lon",
    }
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("_", "").replace("-", "")
    if normalized in _SENSITIVE_EXACT:
        return True
    return any(s in normalized for s in _SENSITIVE_SUBSTRINGS)


def redact(obj: Any) -> Any:
    """Recursively redact dict values whose key matches a sensitive pattern."""
    if isinstance(obj, dict):
        return {
            key: (REDACTED if _is_sensitive_key(key) else redact(value))
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    return obj
