<img src="https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.kia_uvo.total">

## Code Maintainers Wanted

I no longer have a Kia or Hyundai so don't maintain this like I used to. Others who are interested in jumping in are welcome to join the project! Even just pull requests are appreciated!

## Intro

A custom integration for Kia Uvo / Hyundai Bluelink. This project uses our underlying python package: https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hyundai-Kia-Connect&repository=kia_uvo&category=integration)

1. Install [HACS](https://hacs.xyz/) if you don't have it already
2. Open HACS in Home Assistant
3. Search for "Kia Uvo"
4. Click the download button

### Manual

1. Copy the `custom_components/kia_uvo` directory to your `config/custom_components/` directory
2. Restart Home Assistant

### Configuration

After installation, go to **Settings** → **Devices & Services** → **Integrations** and search for **Kia Uvo**. Configure your vehicle using your username and password.

- AU, EU, CA, CH, IN, NZ, BR and US is supported. USA, India, China and Brazil support is limited.
- Genesis Support hasn't been tested and has just been added for Canada only. Feedback would be appreciated!
- Multiple cars and accounts are supported. To add additional accounts just go through setup a second time.
- Reconfigure flow is available from the integration options (change credentials or set PIN).
- Cached update - fetches cached information from servers every 30 minutes. **Configurable**
- Force update - asks your car for the latest data every 4 hours. **Configurable**
- Force update is disabled between 10PM and 6AM by default. **Configurable**
- By default, distance unit is based on HA metric/imperial preference, you need to configure each entity if you would like other units.

## Supported entities

### Sensors

- Odometer, Total Range, EV Range, Fuel Range
- Car Battery Level (12v), EV Battery Level, EV Battery SOH, EV Battery Capacity, EV Battery Remain
- Estimated Charge Duration (current, fast, portable, station)
- EV Target Range (AC/DC charge)
- Air Temperature, Outside Temperature
- Fuel Level
- Total Power Consumed/Regenerated, Power Consumption 30d
- Front/Rear Seat Status and Heater
- Last Service Distance, Next Service Distance
- Engine Type, DTC Count
- EV Charging Power, EV Charging Current
- Geocoded Location (optional, disabled by default)
- Location Last Updated

### EV Diagnostics (CCS2 vehicles)

- EV Battery Pack Voltage
- EV Battery Temperature (min, max, water)
- EV Battery Chiller RPM
- EV Power Consumption (air conditioning, battery cooling, battery heater)
- EV Off-Peak Start/End Time, EV Departure Time (first/second)

### Binary Sensors

- Engine Running, Ignition, Accessory Status
- Defrost, Heated Rear Window, Heated Steering Wheel, Side Mirror Heater
- EV Battery Charging, EV Battery Plugged In, EV Charge Port Open
- EV Battery Winter Mode, EV Battery Precondition Enabled, EV Battery Heating State
- EV V2L/V2X Status
- EV Schedule Charge Enabled, EV Off-Peak Charge Only Enabled
- Door Open/Close (individual doors), Trunk, Hood
- Window Open/Close (individual windows)
- Lock Status (individual doors)
- Tire Pressure Warnings (individual and all)
- Low Fuel Light, Smart Key Battery Warning
- Brake Fluid Warning, Washer Fluid Warning
- Headlamp Status, Turn Signals, Stop Lamps
- Sunroof Open, Sleep Mode
- Transmission Condition

### Switches

- Climate Control
- EV Charging
- EV Schedule Charge Enabled
- EV Off-Peak Charge Only Enabled

### Number Entities

- EV Charge Limits (AC/DC)
- EV V2L Discharge Limit

### Covers

- Individual Window Control (front left, front right, rear left, rear right) — where supported

### Locks

- Door Lock/Unlock

### Climate

- Climate Control (temperature, mode, defrost)

### Buttons

- Force Refresh

### Device Tracker

- Vehicle Location (GPS)

## Supported services

These can be accessed via Developer Tools > Actions, or called from automations.

- `update`: get latest **cached** vehicle data
- `force_update`: ask the vehicle for its latest data — do not overuse!
- `start_climate` / `stop_climate`: start/stop climate control (starts ICE engine in some regions)
- `start_charge` / `stop_charge`: control EV charging
- `set_charge_limits`: set AC/DC charge capacity limits
- `set_charging_current`: set charging current level (100%, 90% or 60%)
- `open_charge_port` / `close_charge_port`: open or close the charge port
- `lock` / `unlock`: lock or unlock the vehicle
- `set_windows`: open/close individual windows (where supported)
- `start_hazard_lights` / `stop_hazard_lights`: hazard lights only
- `start_hazard_lights_and_horn` / `stop_hazard_lights_and_horn`: panic mode
- `schedule_charging_and_climate`: set planned departure schedule
- `start_valet_mode` / `stop_valet_mode`: valet mode

### Service availability by region

| Service                       | EU  | EU(>2023), NZ, AU | CA  | USA Kia | USA Hyundai | USA Genesis | China | India | Brazil |
| ----------------------------- | --- | ----------------- | --- | ------- | ----------- | ----------- | ----- | ----- | ------ |
| Update                        | ✔   | ✔                 | ✔   | ✔       | ✔           | ✔           | ✔     | ✔     | ✔      |
| Force Update                  | ✔   | not tested        | ✔   | ✔       |             |             | ✔     | ✔     | ✔      |
| Lock / Unlock                 | ✔   | ✔                 | ✔   | ✔       | ✔           | ✔           | ✔     | ✔     | ✖      |
| Start / Stop Climate          | ✔   | ✔                 | ✔   | ✔       | ✔           |             | ✔     | ✔     | ✖      |
| Start / Stop Charge           | ✔   | ✔                 | ✔   | ✔       | ✔           |             |       |       | ✖      |
| Set Charge Limits             | ✔   | ✔                 | ✔   | ✔       | ✔           |             |       |       | ✖      |
| Set Charging Current          | ✔   | ✔                 | ✔   | ✔       | ✔           |             |       |       | ✖      |
| Open / Close Charge Port      | ✖   | ✔                 | ✖   | ✖       | ✖           | ✖           | ✖     |       | ✖      |
| Set Windows                   | ✖   | ✔                 | ✖   | ✖       | ✖           | ✖           | ✖     |       | ✖      |
| Start / Stop Hazard Lights    | ✖   | ✔                 | ✖   | ✖       | ✖           | ✖           | ✖     |       | ✖      |
| Start / Stop Hazard + Horn    | ✖   | ✔                 | ✖   | ✖       | ✖           | ✖           | ✖     | ✔     | ✖      |
| Schedule Charging and Climate | ✖   | ✔                 | ✖   | ✖       | ✖           | ✖           | ✖     |       | ✖      |
| Start / Stop Valet Mode       | ✖   | ✔                 | ✖   | ✖       | ✖           | ✖           | ✖     |       | ✖      |

## Screenshots

![Device Details](https://github.com/Hyundai-Kia-Connect/kia_uvo/blob/master/Device%20Details.PNG?raw=true)
![Configuration](https://github.com/Hyundai-Kia-Connect/kia_uvo/blob/master/Configuration.PNG?raw=true)

## Troubleshooting

If you receive an error while trying to login, please go through these steps:

1. This integration supports USA, EU, China, India, Australia, New Zealand, Canada and Brazil. If you are outside these regions, you are welcome to create an issue and become a test user. USA and Brazil coverage is limited.
2. You can enable logging for this integration specifically and share your logs for investigation. To enable logging, click "Enable debug logging" on the integration. It can be accessed via **Settings → System → Logs**.
