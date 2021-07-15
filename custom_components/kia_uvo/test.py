import logging

from datetime import datetime
import push_receiver
import random
import requests
from urllib.parse import parse_qs, urlparse
import uuid

KIA_UVO_BASE_URL_CA: str = "myuvo.ca"
KIA_UVO_API_URL_CA: str = "https://" + KIA_UVO_BASE_URL_CA + "/tods/api/"
KIA_UVO_API_HEADERS_CA = {"from": "SPA", "language": "1", "offset": "0"}
DOMAIN = "KiaUvo"

username = "test"
password = "test"

### Sign In with Email and Password and Get Authorization Code ###

url = KIA_UVO_API_URL_CA + "lgn"
data = {"loginId": username, "password": password}
headers = KIA_UVO_API_HEADERS_CA
headers["accessToken"] = ''
response = requests.post(url, json=data, headers=headers)
print(f"{DOMAIN} - Sign In Response {response.text}")
response = response.json()
access_token = response["result"]["accessToken"]
refresh_token = response["result"]["refreshToken"]
print(f"{DOMAIN} - Access Token Value {access_token}")
print(f"{DOMAIN} - Refresh Token Value {refresh_token}")