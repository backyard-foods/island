import os
import requests
from time import time

class BYFAPIClient:
    def __init__(self):
        self.api_url = os.environ['BYF_API_URL']
        self.anon_key = os.environ['ANON_KEY']
        self.user = os.environ['BYF_USER']
        self.password = os.environ['BYF_PW']
        self.device_id = os.environ['RESIN_DEVICE_UUID']
        self.device_name = os.environ['BALENA_DEVICE_NAME_AT_INIT']
        self.device_type = 'island'
        self.access_token = None
        self.token_expiry = 0 
        self.state = None
        self.auth_retries = 0

    def authenticate(self):
        auth_url = f"{self.api_url}/auth/v1/token?grant_type=password"
        auth_data = {
            "email": self.user,
            "password": self.password
        }
        auth_headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json"
        }
        
        try:
            auth_response = requests.post(auth_url, json=auth_data, headers=auth_headers)
            auth_response.raise_for_status()
            self.access_token = auth_response.json()['access_token']
            self.token_expiry = time() + auth_response.json().get('expires_in', 3600)
            self.auth_retries = 0
        except requests.exceptions.RequestException as e:
            print(f"Authentication failed: {e}")
            raise

    def get_state(self):
        state_url = f"{self.api_url}/functions/v1/state"
        state_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        state_url_params = {
            "deviceId": self.device_id,
            "deviceName": self.device_name,
            "deviceType": self.device_type
        }
        # Check if the token is valid, if not, authenticate
        if not self.is_token_valid():
            self.authenticate()
        
        try:
            state_response = requests.get(state_url, headers=state_headers, params=state_url_params)
            state_response.raise_for_status()
            self.state = state_response.json()
            return self.state
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get device state: {e}")
            if self.auth_retries < 3:
                print(f"Retrying authentication... ({self.auth_retries}/3)")
                self.auth_retries += 1
                self.authenticate()
                return self.get_state()
            raise

    def is_token_valid(self):
        return self.access_token and time() < self.token_expiry

    def notify_print_success(self, order):
        if not self.is_token_valid():
            self.authenticate()

        self.get_state()

        notify_url = f"{self.api_url}/functions/v1/print"
        notify_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        notify_body = {
            "orderName": order,
        }

        try:
            notify_response = requests.post(notify_url, json=notify_body, headers=notify_headers)
            notify_response.raise_for_status()
            print("[Receipt Printer] Successfully notified backend of print completion")
        except requests.exceptions.RequestException as e:
            print(f"[Receipt Printer] Failed to notify backend: {e}")
            raise

    def notify_label_success(self, fulfillment):
        if not self.is_token_valid():
            self.authenticate()

        self.get_state()

        notify_url = f"{self.api_url}/functions/v1/print-label"
        notify_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        notify_body = {
            "fulfillment": fulfillment,
        }

        try:
            notify_response = requests.post(notify_url, json=notify_body, headers=notify_headers)
            notify_response.raise_for_status()
            print("[Label Printer] Successfully notified backend of label print completion")
        except requests.exceptions.RequestException as e:
            print(f"[Label Printer] Failed to notify backend: {e}")
            raise
