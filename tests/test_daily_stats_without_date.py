"""Daily driving stats entries without a date are skipped, not a crash."""

import datetime
from unittest.mock import MagicMock

from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.Vehicle import DailyDrivingStats

from custom_components.kia_uvo.sensor import (
    DailyDrivingStatsEntity,
    TodaysDailyDrivingStatsEntity,
)


def _vehicle() -> Vehicle:
    vehicle = Vehicle(id="v1")
    # Set the backing list: the library's setter sorts by date.
    vehicle._daily_stats = [
        DailyDrivingStats(date=None, total_consumed=1),
        DailyDrivingStats(
            date=datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC), total_consumed=2
        ),
    ]
    return vehicle


def test_daily_stats_skips_entries_without_date() -> None:
    entity = DailyDrivingStatsEntity(MagicMock(), _vehicle())
    assert list(entity.extra_state_attributes) == ["2026-01-02"]


def test_todays_stats_skips_entries_without_date() -> None:
    entity = TodaysDailyDrivingStatsEntity(MagicMock(), _vehicle())
    assert entity.extra_state_attributes["total_consumed"] == 0
