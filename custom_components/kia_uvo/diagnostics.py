"""Diagnostics support for Hyundai / Kia / Genesis Connect.

Downloadable from Settings > Devices & Services > kia_uvo > (menu) > Download
diagnostics. Returns a redacted snapshot of the account's cached state —
parsed Vehicle data, API class, versions, and curated token metadata — with
no fresh API calls (the car is not woken). Users attach this JSON to bug
reports; redaction removes tokens, device id, PIN, and GPS coordinates
before the dump leaves their Home Assistant instance.
"""

from __future__ import annotations

from dataclasses import asdict
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_REGION, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import (
    CONF_BRAND,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_NO_FORCE_REFRESH_HOUR_FINISH,
    CONF_NO_FORCE_REFRESH_HOUR_START,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
    DEFAULT_ENABLE_GEOLOCATION_ENTITY,
    DEFAULT_FORCE_REFRESH_INTERVAL,
    DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH,
    DEFAULT_NO_FORCE_REFRESH_HOUR_START,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_EMAIL_WITH_GEOCODE_API,
    DOMAIN,
)
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .redact import redact


def _token_meta(token: Any) -> dict[str, Any]:
    """Secret-free view of the Token: expiries, MQTT metadata, device-id
    presence. The raw access/refresh/control tokens, PIN, and stamp never
    leave the dump.
    """
    if token is None:
        return {}
    return {
        "valid_until": token.valid_until.isoformat() if token.valid_until else None,
        "ccs_valid_until": (
            token.ccs_token_valid_until.isoformat()
            if getattr(token, "ccs_token_valid_until", None)
            else None
        ),
        "control_expiry": getattr(token, "control_token_expiry", 0),
        "mqtt_client_id": getattr(token, "mqtt_client_id", None),
        "mqtt_broker_host": getattr(token, "mqtt_broker_host", None),
        "mqtt_broker_port": getattr(token, "mqtt_broker_port", None),
        "device_present": bool(getattr(token, "device_id", None)),
    }


def _config_options(entry: ConfigEntry) -> dict[str, Any]:
    """Show effective values (option or default) so the dump reflects what
    the integration runs with, not a field of nulls.
    """
    return {
        "scan_interval": entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        "force_refresh_interval": entry.options.get(
            CONF_FORCE_REFRESH_INTERVAL, DEFAULT_FORCE_REFRESH_INTERVAL
        ),
        "no_force_refresh_hour_start": entry.options.get(
            CONF_NO_FORCE_REFRESH_HOUR_START, DEFAULT_NO_FORCE_REFRESH_HOUR_START
        ),
        "no_force_refresh_hour_finish": entry.options.get(
            CONF_NO_FORCE_REFRESH_HOUR_FINISH, DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH
        ),
        "enable_geolocation_entity": entry.options.get(
            CONF_ENABLE_GEOLOCATION_ENTITY, DEFAULT_ENABLE_GEOLOCATION_ENTITY
        ),
        "use_email_with_geocode_api": entry.options.get(
            CONF_USE_EMAIL_WITH_GEOCODE_API, DEFAULT_USE_EMAIL_WITH_GEOCODE_API
        ),
    }


def _vehicles_payload(
    coordinator: HyundaiKiaConnectDataUpdateCoordinator,
) -> list[dict[str, Any]]:
    vm = coordinator.vehicle_manager
    vehicles: list[dict[str, Any]] = []
    for vehicle_id, vehicle in vm.vehicles.items():
        try:
            vehicles.append({"vehicle_id": vehicle_id, "data": asdict(vehicle)})
        except Exception as exc:  # noqa: BLE001 — diagnostics must be resilient
            vehicles.append(
                {"vehicle_id": vehicle_id, "error": f"{type(exc).__name__}: {exc}"}
            )
    return vehicles


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return a redacted diagnostics snapshot for this config entry."""
    # kia_uvo stores its coordinator under config_entry.unique_id (see
    # __init__.py async_setup_entry), not entry_id.
    coordinator: HyundaiKiaConnectDataUpdateCoordinator = hass.data[DOMAIN][
        entry.unique_id
    ]
    vm = coordinator.vehicle_manager
    integration = await async_get_integration(hass, DOMAIN)

    try:
        library_version: str | None = await hass.async_add_executor_job(
            pkg_version, "hyundai_kia_connect_api"
        )
    except PackageNotFoundError:
        library_version = None

    payload: dict[str, Any] = {
        "region": entry.data.get(CONF_REGION),
        "brand": entry.data.get(CONF_BRAND),
        "api_class": type(vm.api).__name__,
        "integration_version": integration.version,
        "library_version": library_version,
        "config_options": _config_options(entry),
        "auth": _token_meta(vm.token),
        "vehicle_count": len(vm.vehicles),
    }
    # Redact only the uncontrolled Vehicle data (raw asdict: GPS, VIN, geocode
    # address, region-specific field names). Whole-payload redaction collides
    # on constructed key names like the "email" in `use_email_with_geocode_api`.
    vehicles = _vehicles_payload(coordinator)
    payload["vehicles"] = [redact(v) for v in vehicles]
    return payload
