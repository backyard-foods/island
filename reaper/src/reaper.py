import os
import time
import requests
from threading import Thread

REBOOT_AFTER_OFFLINE_MINS = 3

class Reaper:
    def __init__(self):
        self.last_keepalive = time.time()
        self.running = True
        self.scheduled_reboot = os.environ.get('SCHEDULED_REBOOT_TIME_UTC', '10:00')
        print(f"Reaper initialized: {self.running}")
        print(f"Scheduled UTC reboot time: {self.scheduled_reboot}")
        print(f"Current UTC time: {time.strftime('%H:%M')}")

    def keepalive(self):
        self.last_keepalive = time.time()
        return True

    def reboot_if_offline(self):
        if time.time() - self.last_keepalive > REBOOT_AFTER_OFFLINE_MINS * 60:
            self.reboot()
    
    def reboot(self):
        print("Rebooting device")

        supervisor_address = os.environ['BALENA_SUPERVISOR_ADDRESS']
        api_key = os.environ['BALENA_SUPERVISOR_API_KEY']

        url = f"{supervisor_address}/v1/reboot?apikey={api_key}"

        try:
            response = requests.post(url)
            response.raise_for_status()
            print("Reboot request sent successfully")
        except requests.exceptions.RequestException as e:
            print(f"Failed to reboot: {e}")

    def reboot_if_scheduled(self):
        current_time = time.strftime('%H:%M')
        if current_time == self.scheduled_reboot:
            print(f"Rebooting device at scheduled UTC time ({current_time}) in 1 minute")
            time.sleep(60)
            self.reboot()

    def __enter__(self):
        self.running = True
        Thread(target=self.monitor).start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.running = False

    def monitor(self):
        while self.running:
            self.reboot_if_offline()
            self.reboot_if_scheduled()
            time.sleep(3)
