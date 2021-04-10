from datetime import datetime

class Token(object):
    def __init__(self, access_token, refresh_token, device_id, vehicle_name, vehicle_id, vehicle_model, vehicle_registration_date, valid_until):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.device_id = device_id
        self.vehicle_name = vehicle_name
        self.vehicle_id = vehicle_id
        self.vehicle_model = vehicle_model
        self.vehicle_registration_date = vehicle_registration_date
        self.valid_until = valid_until
        if self.valid_until is None:
            self.valid_until = datetime.min