import os
import requests
import time
from temp_sensor_manager import TempSensorManager
from utils import restart_service

POLL_INTERVAL_S = 10
ERROR_POLL_INTERVAL_S = 5
LABEL_PRINTER_RESTART_TIME_S = 15
LABEL_PRINTER_TIME_BETWEEN_RESTARTS_S = 60
RECEIPT_PRINTER_RESTART_TIME_S = 15
RECEIPT_PRINTER_TIME_BETWEEN_RESTARTS_S = 60

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
        self.poll_interval = POLL_INTERVAL_S
        self.temp_sensor_manager = TempSensorManager()
        self.temp_sensor_manager.start_temperature_checking()
        self.label_printer_status = None
        self.label_printer_reason = None
        self.label_printer_last_restart = 0
        self.receipt_printer_status = None
        self.receipt_printer_reason = None
        self.receipt_printer_last_restart = 0

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
            self.token_expiry = time.time() + auth_response.json().get('expires_in', 3600)
            self.auth_retries = 0
        except requests.exceptions.RequestException as e:
            print(f"Authentication failed: {e}")
            raise

    def get_state(self):
        self.handle_printer_status()
        
        state_url = f"{self.api_url}/functions/v1/state"
        state_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        state_url_params = {
            "deviceId": self.device_id,
            "deviceName": self.device_name,
            "deviceType": self.device_type,
            "labelPrinterStatus": self.label_printer_status,
            "labelPrinterReason": self.label_printer_reason,
            "receiptPrinterStatus": self.receipt_printer_status,
            "receiptPrinterReason": self.receipt_printer_reason,
        }

        # Check if the token is valid, if not, authenticate
        if not self.is_token_valid():
            self.authenticate()
        
        try:
            print(f"Getting device state from {state_url}")
            temperature_events = self.temp_sensor_manager.get_events()
            state_response = requests.post(state_url, headers=state_headers, params=state_url_params, json=temperature_events)
            state_response.raise_for_status()
            self.state = state_response.json()
            self.process_state()
            return self.state
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get device state: {e}")
            if self.auth_retries < 3:
                print(f"Retrying authentication... ({self.auth_retries}/3)")
                self.auth_retries += 1
                self.authenticate()
                return self.get_state()
            raise

    def process_state(self):
        if self.state and 'store' in self.state:
            store_open = self.state['store'].get('open', False)
            state = 'on' if store_open else 'off'

            try:
                print(f"Making sure lights are {state}")
                response = requests.get(f'http://porchlight:1234/{state}')
                response.raise_for_status()
                return True
            except requests.RequestException as e:
                print(f"Error sending light {state} request: {str(e)}")
                return False
        return False

    def is_token_valid(self):
        return self.access_token and time.time() < self.token_expiry
    
    def get_access_token(self):
        if not self.is_token_valid():
            self.authenticate()
        return self.access_token

    def handle_printer_status(self):
        self.handle_label_printer_status()
        self.handle_receipt_printer_status()
        if self.label_printer_status == "ready" and self.receipt_printer_status == "ready":
            print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ Both printers are ready, setting poll interval to 20s")
            self.poll_interval = POLL_INTERVAL_S
        else:
            print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ One or both printers are not ready, setting poll interval to 5s")
            self.poll_interval = ERROR_POLL_INTERVAL_S
    
    def handle_receipt_printer_status(self):
        time_since_restart = time.time() - self.receipt_printer_last_restart
        
        if time_since_restart < RECEIPT_PRINTER_RESTART_TIME_S:
            return self.receipt_printer_status, self.receipt_printer_reason
        
        status = None
        reason = None

        try:
            response = requests.get('http://receipt-printer:1234/status')
            response.raise_for_status()
            status = response.json().get('status', None)
            reason = response.json().get('reason', None)
        except requests.RequestException as e:
            print(f"Error getting receipt printer status: {str(e)}")
            status = "service_offline"
            reason = str(e)
        self.receipt_printer_status = status
        self.receipt_printer_reason = reason

        if status == "not_found" and time_since_restart > RECEIPT_PRINTER_TIME_BETWEEN_RESTARTS_S:
            return self.restart_receipt_printer()
        
        return self.receipt_printer_status, self.receipt_printer_reason
    
    def restart_receipt_printer(self):
        self.receipt_printer_last_restart = time.time()
        self.receipt_printer_status = "service_restarting"
        restart_service("receipt-printer")
        return self.receipt_printer_status, self.receipt_printer_reason
    
    def notify_print_success(self, order):
        if not self.is_token_valid():
            self.authenticate()

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

    def handle_label_printer_status(self):
        time_since_restart = time.time() - self.label_printer_last_restart
        
        if time_since_restart < LABEL_PRINTER_RESTART_TIME_S:
            return self.label_printer_status, self.label_printer_reason
        
        status = None
        reason = None

        try:
            response = requests.get('http://label-printer:1234/status')
            response.raise_for_status()
            status = response.json().get('status', None)
            reason = response.json().get('reason', None)
        except requests.RequestException as e:
            print(f"Error getting label printer status: {str(e)}")
            status = "service_offline"
            reason = str(e)
        self.label_printer_status = status
        self.label_printer_reason = reason

        if status == "not_found" and time_since_restart > LABEL_PRINTER_TIME_BETWEEN_RESTARTS_S:
            return self.restart_label_printer()
        
        return self.label_printer_status, self.label_printer_reason
    
    def restart_label_printer(self):
        self.label_printer_last_restart = time.time()
        self.label_printer_status = "service_restarting"
        restart_service("label-printer")
        return self.label_printer_status, self.label_printer_reason
    
    def notify_label_success(self, fulfillment):
        if not self.is_token_valid():
            self.authenticate()

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

    def notify_wave_status(self, status):
        if not self.is_token_valid():
            self.authenticate()

        notify_url = f"{self.api_url}/functions/v1/wave-status"
        notify_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        notify_body = {
            "status": status,
        }

        try:
            notify_response = requests.post(notify_url, json=notify_body, headers=notify_headers)
            notify_response.raise_for_status()
            print("[Wave] Successfully notified backend of wave status")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[Wave] Failed to notify backend: {e}")
            return False

    def start_polling(self):
        while True:
            try:
                self.get_state()
            except Exception as e:
                print(f"Error getting state: {e}")
            time.sleep(self.poll_interval)
