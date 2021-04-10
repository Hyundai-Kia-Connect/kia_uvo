I have baked a custom integration for EU Kia Uvo, this will be working for new account types. Thanks for your hard work [@wcomartin](https://github.com/wcomartin/kiauvo)

Warning ahead; this is pre-alpha phase, please do not expect something fully functional, I will improve the integration by time.

You can install this either manually copying files or using HACS. Configuration can be done on UI, you need to enter your username and password, (I know, translations are missing!). 

- it will only fetch values for the first car, I am not sure if there are people outside using Kia Uvo with multiple cars :)
- update - It will fetch the cached information every 30 minutes from Kia Servers.
- force update - It will ask your car for the latest data every 2 hours. 
- It will not force update between 10PM to 6AM. I am trying to be cautios here.

Supported entities;
- Car Battery Level (12v), EV Battery Level
- Doors, Trunk and Hood Open/Close Status
- Door Lock
- Engine Status
- Location (over GPS)
- Odemeter
- EV Range, Fuel Range, Total Range
- Last Update

I have posted an example screenshot from my own car.

![Device Details](https://github.com/fuatakgun/kia_uvo/blob/master/Device%20Details.PNG?raw=true)
