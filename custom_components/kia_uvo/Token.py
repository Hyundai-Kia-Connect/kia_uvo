from datetime import datetime
from .const import DATE_FORMAT


class Token(object):
    def __init__(self, data):
        self.__dict__ = data
        if "stamp" not in self.__dict__:
            self.expire()

    def set(self, access_token, refresh_token, device_id, vehicle_name, vehicle_id, vehicle_model, vehicle_registration_date, valid_until, stamp):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.device_id = device_id
        self.vehicle_name = vehicle_name
        self.vehicle_id = vehicle_id
        self.vehicle_model = vehicle_model
        self.vehicle_registration_date = vehicle_registration_date
        self.valid_until = valid_until
        self.stamp = stamp
        if self.valid_until is None or self.stamp is None:
            self.expire()

    def expire(self):
        self.valid_until = datetime.min.strftime(DATE_FORMAT)


class UsaToken(Token):
    def __init__(self, sid, vehicle_vin, vehicle_id, vehicle_name, vehicle_key):
        self.sid = sid
        self.vin = vehicle_vin
        self.vehicle_id = vehicle_id
        self.vehicle_name = vehicle_name
        self.vehicle_key = vehicle_key

    def expire(self):
        pass
