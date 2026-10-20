"""Scheduled-maintenance helpers for regions that report service intervals.

The India maintenance-alert endpoint gives each item's distance and time
interval but no service history, so "due" is derived from the odometer and
the vehicle's age against the interval from new. An item is due once the
odometer or the age passes the interval; after the first service the car
should be re-serviced each interval, but the API never tells us a service
happened, so these follow the schedule from new. Kept free of Home
Assistant imports so they are easy to test.
"""

from __future__ import annotations

import datetime as dt
import re

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.Vehicle import MaintenanceAlertItem

_REG_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def item_slug(name: str) -> str:
    """A stable entity-key slug for a maintenance item name."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _registration_date(vehicle: Vehicle) -> dt.datetime | None:
    reg = getattr(vehicle, "registration_date", None)
    if not reg:
        return None
    for fmt in _REG_FORMATS:
        try:
            return dt.datetime.strptime(reg, fmt)
        except (ValueError, TypeError):
            continue
    return None


def vehicle_age_months(vehicle: Vehicle, now: dt.datetime) -> int | None:
    """Whole months since registration, or None when the date is unknown."""
    reg = _registration_date(vehicle)
    if reg is None:
        return None
    months = (now.year - reg.year) * 12 + (now.month - reg.month)
    if now.day < reg.day:
        months -= 1
    return max(months, 0)


def _odometer_km(vehicle: Vehicle) -> float | None:
    odo = vehicle.odometer
    return float(odo) if isinstance(odo, (int, float)) else None


def remaining_km(item: MaintenanceAlertItem, vehicle: Vehicle) -> float | None:
    """Distance to the interval; negative means overdue. None if unknown."""
    odo = _odometer_km(vehicle)
    if not item.interval_km or odo is None:
        return None
    return float(item.interval_km) - odo


def remaining_months(
    item: MaintenanceAlertItem, vehicle: Vehicle, now: dt.datetime
) -> int | None:
    """Months to the interval; negative means overdue. None if unknown."""
    age = vehicle_age_months(vehicle, now)
    if not item.interval_months or age is None:
        return None
    return int(item.interval_months) - age


def is_due(item: MaintenanceAlertItem, vehicle: Vehicle, now: dt.datetime) -> bool:
    """True once the odometer or the age reaches the item's interval."""
    rem_km = remaining_km(item, vehicle)
    rem_months = remaining_months(item, vehicle, now)
    return (rem_km is not None and rem_km <= 0) or (
        rem_months is not None and rem_months <= 0
    )
