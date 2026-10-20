"""Trip statistics helpers for regions whose API reports trip history.

The coordinator keeps, per vehicle, ``month_trip_info`` for the current month
and ``day_trip_info`` for the most recent day with trips. These helpers turn
that into "today", "this month" and "last trip" values. Kept free of Home
Assistant imports so they are easy to test.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.const import REGION_INDIA, REGIONS
from hyundai_kia_connect_api.Vehicle import TripInfo

# Regions where trip history has been verified against a live account.
TRIP_STATS_REGIONS: frozenset[str] = frozenset({REGION_INDIA})


def region_supports_trip_stats(region: Any) -> bool:
    """Return True when trip stats are enabled for this config region id."""
    return REGIONS.get(region) in TRIP_STATS_REGIONS


def latest_trip_day(vehicle: Vehicle) -> str | None:
    """Most recent yyyymmdd in the current month with at least one trip."""
    month = vehicle.month_trip_info
    if month is None:
        return None
    days = [d.yyyymmdd for d in month.day_list if d.trip_count]
    return max(days) if days else None


def month_signature(vehicle: Vehicle) -> tuple[Any, ...] | None:
    """Changes whenever a trip is added to the current month."""
    month = vehicle.month_trip_info
    if month is None:
        return None
    return (
        month.yyyymm,
        month.summary.distance if month.summary else None,
        tuple((d.yyyymmdd, d.trip_count) for d in month.day_list),
    )


def today_summary(vehicle: Vehicle, today: str) -> TripInfo | None:
    """Today's trip totals, or None when there were no trips today."""
    day = vehicle.day_trip_info
    if day is None or day.yyyymmdd != today:
        return None
    return day.summary


def today_trip_count(vehicle: Vehicle, today: str) -> int:
    """Number of trips today (0 when none)."""
    month = vehicle.month_trip_info
    if month is None:
        return 0
    return sum(d.trip_count or 0 for d in month.day_list if d.yyyymmdd == today)


def month_trip_count(vehicle: Vehicle) -> int:
    """Number of trips so far this month (0 when none)."""
    month = vehicle.month_trip_info
    if month is None:
        return 0
    return sum(d.trip_count or 0 for d in month.day_list)


def last_trip(vehicle: Vehicle) -> TripInfo | None:
    """The newest trip on the most recent day with trips."""
    day = vehicle.day_trip_info
    if day is None or not day.trip_list:
        return None
    return day.trip_list[0]  # Vehicle keeps trip_list newest-first


def _trip_time(
    vehicle: Vehicle, hhmmss: str | None, tz: dt.tzinfo
) -> dt.datetime | None:
    day = vehicle.day_trip_info
    if day is None or not hhmmss or not day.yyyymmdd:
        return None
    try:
        return dt.datetime.strptime(day.yyyymmdd + hhmmss, "%Y%m%d%H%M%S").replace(
            tzinfo=tz
        )
    except ValueError:
        return None


def last_trip_start(vehicle: Vehicle, tz: dt.tzinfo) -> dt.datetime | None:
    """Start time of the last trip, in the API's timezone."""
    trip = last_trip(vehicle)
    return _trip_time(vehicle, trip.hhmmss if trip else None, tz)


def last_trip_end(vehicle: Vehicle, tz: dt.tzinfo) -> dt.datetime | None:
    """End time of the last trip, in the API's timezone."""
    trip = last_trip(vehicle)
    end = _trip_time(vehicle, trip.end_hhmmss if trip else None, tz)
    start = last_trip_start(vehicle, tz)
    if end is not None and start is not None and end < start:
        end += dt.timedelta(days=1)  # trip ran past midnight
    return end
