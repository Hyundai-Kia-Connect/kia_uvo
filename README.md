<img src="https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.kia_uvo.total">

## Code Maintainers Wanted

I no longer have a Kia or Hyundai so don't maintain this like I used to. Others who are interested in jumping in are welcome to join the project! Even just pull requests are appreciated!

## Intro

I have baked a custom integration for Kia Uvo / Hyundai Bluelink, this will be working for new account types. Thanks for your hard work [@wcomartin](https://github.com/wcomartin/kiauvo). This project was mostly inspired by his [home assistant integration](https://github.com/wcomartin/kia_uvo). This now uses our underlying python package: https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api.

## Installation

Install the software by using HACS or manually copying files into the `custom_components` subdirectory. Next, go to **Settings**, then **Devices & services** and in the **Integrations** section search for **Kia uvo** and configure your vehicle using your username and password (I know, translations are missing, a PR for this would be great!).

- AU, EU, CA and US is supported by this. USA and China support is limited.
- Genesis Support hasn't been tested and has just been added for Canada only. Feedback would be appreciated!
- Multiple cars and accounts are supported. To add additional accounts just go through setup a second time.
- update - It will fetch the cached information every 30 minutes from Kia Uvo / Hyundai Bluelink Servers. **Now Configurable**
- force update - It will ask your car for the latest data every 4 hours. **Now Configurable**
- It will not force update between 10PM to 6AM. I am trying to be cautios here. **Now Configurable**
- By default, distance unit is based on HA metric/imperial preference, you need to configure each entity if you would like other units.

## Supported entities

- Air Conditioner Status, Defroster Status, Set Temperature
- Heated Rear Window, Heated Steering Wheel
- Car Battery Level (12v), EV Battery Level, Remaining Time to Full Charge
- Tire Pressure Warnings (individual and all)
- Charge Status and Plugged In Status
- Low Fuel Light Status (for PHEV and IC)
- Doors, Trunk, Window and Hood Open/Close Status
- Locking and Unlocking
- Engine Status
- Location/Coordinates (over GPS) and Geocoded Location using OpenStreetMap (optional, disabled by default)
- Last Service and Next Service in Canada
- Odometer, EV Range (for PHEV and EV), Fuel Range (for PHEV and IC), Total Range (for PHEV and EV)
- Latest Update
- cache update interval, force update interval, blackout start and finish hours

## Supported services

These can be access by going to the developer tools followed by actions. These can also be called via automation.

- update: get latest **cached** vehicle data
- force_update: this will make a call to your vehicle to get its latest data, do not overuse this!
- start_climate / stop_climate: Starts the ICE engine in some regions or starts EV climate.
- start_charge / stop_charge: You can control your charging using these services
- set_charge_limits: You can control your charging capacity limits using this services
- set_charging_current: You can control the charging current level (100%, 90% or 60%)
- open_charge_port / close_charge_port: Open or close the charge port.

| Service                    | EU  | EU(>2023)  | CA  | USA Kia | USA Hyundai | USA Genesis | China |
| -------------------------- | --- | ---------- | --- | ------- | ----------- | ----------- | ----- |
| Update                     | ✔  | ✔         | ✔  | ✔      | ✔          | ✔          | ✔    |
| Force Update               | ✔  | not tested | ✔  | ✔      |             |             | ✔    |
| Lock Unlock                | ✔  | ✔         | ✔  | ✔      | ✔          | ✔          | ✔    |
| start stop climate         | ✔  | ✔         | ✔  | ✔      | ✔          |             | ✔    |
| start stop charge          | ✔  | ✔         | ✔  | ✔      | ✔          |             |       |
| set charge limits          | ✔  | not tested | ✔  | ✔      | ✔          |             |       |
| open and close charge port | ✖  | ✔         | ✖  | ✖      | ✖          | ✖          | ✖    |

I have posted an example screenshot from my own car.

![Device Details](https://github.com/Hyundai-Kia-Connect/kia_uvo/blob/master/Device%20Details.PNG?raw=true)
![Configuration](https://github.com/Hyundai-Kia-Connect/kia_uvo/blob/master/Configuration.PNG?raw=true)

## Troubleshooting

If you receive an error while trying to login, please go through these steps;

1. As of now, integration only supports USA, EU and CAD region, so if you are outside, you are more than welcome to create an issue and become a test user for changes to expand coverage. USA coverage isn't complete.
2. If you are in EU, please log out from UVO app and login again. While logging in, if your account was created in legacy UVO servers, they will be migrated to new Kia Uvo / Hyundai Bluelink servers. Related Issue: https://github.com/Hyundai-Kia-Connect/kia_uvo/issues/22
3. If you have migrated recently, you might need to wait one day to try again. Related Issue: https://community.home-assistant.io/t/kia-uvo-integration-pre-alpha/297927/12?u=fuatakgun
4. As a last resort, please double check your account credentials or you can create a new account and share your car from main account to new account.
5. You can enable logging for this integration specifically and share your logs, so I can have a deep dive investigation. To enable logging click "Enable debug logging" on the integration. It can be access via "Settings -> System -> Logs"
