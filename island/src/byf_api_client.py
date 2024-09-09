import os
import requests
from time import time

class BYFAPIClient:
    def __init__(self):
        self.api_url = os.environ['BYF_API_URL']
        self.anon_key = os.environ['ANON_KEY']
        self.user = os.environ['BYF_USER']
        self.password = os.environ['BYF_PW']
        self.access_token = None
        self.token_expiry = 0  # Add this line

    def authenticate(self):
        print("Authenticating with BYF API")
        print(f"API URL: {self.api_url}")
        print(f"Anon Key: {self.anon_key}")
        print(f"User: {self.user}")
        print(f"Password: {self.password}")
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
            self.token_expiry = time() + auth_response.json().get('expires_in', 3600)  # Add this line
        except requests.exceptions.RequestException as e:
            print(f"Authentication failed: {e}")
            raise

    def is_token_valid(self):
        return self.access_token and time() < self.token_expiry

    def notify_print_success(self, order):
        if not self.is_token_valid():
            self.authenticate()

        notify_url = f"{self.api_url}/functions/v1/print"
        notify_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        notify_body = {
            "order": order,
        }

        print(f"Notifying backend of print completion for order: {order}")
        print(f"Notify URL: {notify_url}")
        print(f"Notify Headers: {notify_headers}")
        print(f"Notify Body: {notify_body}")
        try:
            notify_response = requests.post(notify_url, json=notify_body, headers=notify_headers)
            notify_response.raise_for_status()
            print("Successfully notified backend of print completion")
        except requests.exceptions.RequestException as e:
            print(f"Failed to notify backend: {e}")
            raise
