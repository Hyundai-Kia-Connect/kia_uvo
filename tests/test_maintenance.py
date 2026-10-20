"""Scheduled-maintenance helpers and binary sensors (India).

Mirrors a live Kia India Seltos: odometer 11,192 km, registered 2025-09-01,
checked 2026-10-20 (~13.6 months), so the 10,000 km / 12-month items are due
and the longer-interval items are not — matching the app's Maintenance Alert.
"""

import datetime as dt

from conftest import make_coordinator, make_hass
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.Vehicle import MaintenanceAlertItem

from custom_components.kia_uvo import binary_sensor as binary_platform
from custom_components.kia_uvo import maintenance

NOW = dt.datetime(2026, 10, 20, 12, 0)

ITEMS = [
    MaintenanceAlertItem(name="Engine oil", interval_km=10000, interval_months=12),
    MaintenanceAlertItem(name="Oil Filter", interval_km=10000, interval_months=12),
    MaintenanceAlertItem(
        name="Tire position change", interval_km=10000, interval_months=12
    ),
    MaintenanceAlertItem(name="Wheel alignment", interval_km=10000, interval_months=12),
    MaintenanceAlertItem(
        name="Cooling water", interval_km=210000, interval_months=None
    ),
    MaintenanceAlertItem(name="Ignition plug", interval_km=60000, interval_months=None),
    MaintenanceAlertItem(
        name="Antimicrobial filter", interval_km=20000, interval_months=24
    ),
]


def _seltos(odometer: float = 11192, reg: str = "2025-09-01 09:19:43.418") -> Vehicle:
    vehicle = Vehicle(id="v1", name="SELTOS", model="SELTOS")
    vehicle.registration_date = reg
    if odometer is not None:
        vehicle.odometer = (odometer, "km")
    vehicle.maintenance_alerts = list(ITEMS)
    return vehicle


def _by_name(name: str) -> MaintenanceAlertItem:
    return next(i for i in ITEMS if i.name == name)


# --- helpers --------------------------------------------------------------


def test_age_in_months():
    assert maintenance.vehicle_age_months(_seltos(), NOW) == 13
    assert maintenance.vehicle_age_months(_seltos(reg=""), NOW) is None


def test_remaining_and_due_match_app_warnings():
    vehicle = _seltos()
    # Four 10k/12mo items overdue on both distance and time.
    for name in ("Engine oil", "Oil Filter", "Tire position change", "Wheel alignment"):
        item = _by_name(name)
        assert maintenance.remaining_km(item, vehicle) == 10000 - 11192
        assert maintenance.remaining_months(item, vehicle, NOW) == 12 - 13
        assert maintenance.is_due(item, vehicle, NOW) is True
    # Longer-interval items not due.
    for name in ("Cooling water", "Ignition plug", "Antimicrobial filter"):
        assert maintenance.is_due(_by_name(name), vehicle, NOW) is False


def test_time_only_due_when_distance_fine():
    # 12-month item on a low-mileage year-old car: due by time, not distance.
    vehicle = _seltos(odometer=3000)
    item = _by_name("Engine oil")
    assert maintenance.remaining_km(item, vehicle) == 7000
    assert maintenance.is_due(item, vehicle, NOW) is True


def test_no_odometer_or_date_is_not_due():
    vehicle = _seltos(odometer=None, reg="")
    assert maintenance.is_due(_by_name("Engine oil"), vehicle, NOW) is False
    assert maintenance.remaining_km(_by_name("Engine oil"), vehicle) is None


# --- entities -------------------------------------------------------------


async def _maintenance_sensors(vehicle: Vehicle) -> dict:
    hass, config_entry = make_hass(make_coordinator(vehicle))
    created: list = []
    await binary_platform.async_setup_entry(hass, config_entry, created.extend)
    return {
        e._item_name: e
        for e in created
        if isinstance(e, binary_platform.MaintenanceAlertBinarySensor)
    }


async def test_one_sensor_per_item_with_app_labels():
    sensors = await _maintenance_sensors(_seltos())
    assert set(sensors) == {i.name for i in ITEMS}
    assert sensors["Tire position change"].name == "Tyre Rotation"
    assert sensors["Cooling water"].name == "Engine Coolant"
    assert sensors["Engine oil"].unique_id == "kia_uvo_v1_maintenance_engine_oil"


async def test_sensor_state_and_attributes():
    sensors = await _maintenance_sensors(_seltos())
    oil = sensors["Engine oil"]
    assert oil.is_on is True
    assert oil.device_class == binary_platform.BinarySensorDeviceClass.PROBLEM
    assert oil.extra_state_attributes == {
        "interval_km": 10000,
        "interval_months": 12,
        "remaining_km": -1192,
        "remaining_months": -1,
    }
    coolant = sensors["Cooling water"]
    assert coolant.is_on is False
    assert "remaining_months" not in coolant.extra_state_attributes  # no time interval


async def test_no_sensors_without_maintenance_data():
    vehicle = Vehicle(id="v2", name="X", model="EV6")
    assert await _maintenance_sensors(vehicle) == {}


async def test_sensor_unavailable_when_item_disappears():
    vehicle = _seltos()
    sensors = await _maintenance_sensors(vehicle)
    oil = sensors["Engine oil"]
    oil.coordinator.last_update_success = True
    vehicle.maintenance_alerts = [i for i in ITEMS if i.name != "Engine oil"]
    assert oil.available is False
    assert oil.is_on is None
