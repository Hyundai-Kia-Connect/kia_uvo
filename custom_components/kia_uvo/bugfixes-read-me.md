# Bugfixes — `basbugfixes` branch

## P0 — Critical (Incorrect state / crashes)

### Seat heater binary sensors always report ON
**File:** `custom_components/kia_uvo/binary_sensor.py`

The four seat heater binary sensors used the raw `front_left_seat_status` (etc.) string as a boolean. In Python, any non-empty string — including `"Off"` — is truthy, so every seat heater was always reported as **on**.

**Fix:** Changed the lambdas to explicitly check `not in (None, "Off", "0", 0, False)` so they only report on when the seat is actually heating or cooling.

---

### Service calls crash with `UnboundLocalError`
**File:** `custom_components/kia_uvo/services.py`

Both `_get_vehicle_id_from_device` and `_get_coordinator_from_device` could crash when:
- `device_id` was not provided in the service call
- The device entry was not found in the registry
- No matching domain identifier was found on the device
- No matching config entry was found

In each case, the code would either access an undefined variable or call `.unique_id` on `None`.

**Fix:** Added explicit validation at each step, raising `HomeAssistantError` with a clear message instead of crashing.

---

## P1 — High (Deprecation / data integrity)

### `state_attributes` → `extra_state_attributes`
**File:** `custom_components/kia_uvo/sensor.py`

`state_attributes` is deprecated in Home Assistant. It was used in four places:
- `HyundaiKiaConnectSensor` (geocode and DTC attributes)
- `VehicleEntity` (vehicle data dump)
- `DailyDrivingStatsEntity` (daily stats history)
- `TodaysDailyDrivingStatsEntity` (today's stats)

**Fix:** Renamed all four properties to `extra_state_attributes`.

---

### Deprecated entity registry API
**File:** `custom_components/kia_uvo/__init__.py`

The migration code used `hass.helpers.entity_registry.async_get(hass)` which is deprecated and will eventually be removed.

**Fix:** Replaced with the modern import pattern:
```python
from homeassistant.helpers import entity_registry as er
registry = er.async_get(hass)
```

---

### Missing exception chain on `ConfigEntryNotReady`
**File:** `custom_components/kia_uvo/__init__.py`

```python
raise ConfigEntryNotReady(f"Config Not Ready: {ex}")
```
was missing `from ex`, which loses the original traceback and makes debugging harder.

**Fix:** Added `from ex` to preserve the exception chain.

---

### Number entity float→int type mismatch
**File:** `custom_components/kia_uvo/number.py`

Home Assistant's `NumberEntity` delivers `value` as a `float`, but the underlying API expects `int` for charge limits and V2L limits. The existing vehicle attribute values (`ev_charge_limits_ac`, `ev_charge_limits_dc`) were also passed without casting.

**Fix:** Wrapped all values in `int()` before passing to the API:
```python
ac = int(value)
dc = int(self.vehicle.ev_charge_limits_dc)
```

---

### Silent stale data after force refresh failure
**File:** `custom_components/kia_uvo/coordinator.py`

When the force refresh failed but the cached fallback succeeded, no warning was surfaced — entities silently showed stale data. The logging also used f-strings (defeating lazy evaluation) and redundant `traceback.format_exc()` calls.

**Fix:**
- Added `_LOGGER.warning()` calls so users can see when cached data is being used
- Used proper `%s` format strings for logging
- Chained exceptions with `from cached_err`
- Removed the unused `import traceback`
