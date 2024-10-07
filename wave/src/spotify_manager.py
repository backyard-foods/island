import subprocess
import threading
import time
from collections import deque
from enum import Enum
import requests

LOG_PREFIX = "[spotify-manager]"
LOG_PREFIX_LIBRESPOT = "[spotify-manager-librespot]"

COMMAND_START_FROM_CACHE = "librespot -n island -c /spotify-cache"
COMMAND_START_WITH_ACCESS_TOKEN = "librespot -n island -c /spotify-cache -k"

STDOUT_IGNORE_LIST = [
    "WARN",
    "underrun"
]
STDOUT_AUTH_SUCCESS = "Authenticated"

MAX_RETRIES = 5
RETRY_WINDOW_SECONDS = 600
ACCESS_TOKEN_CACHE_SECONDS = 900

STATUS_NOTIFICATION_RETRY_INTERVAL_SECONDS = 30

class SpotifyStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    STARTING = "starting"
    NEEDS_AUTH = "needs_auth"
    ERROR = "error"

class SpotifyManager:
    def __init__(self):
        self.process = None
        self.monitor_thread = None
        self.status_thread = None
        self.retry_times = deque(maxlen=MAX_RETRIES)
        self.terminated = False
        self.access_token = None
        self.access_token_expiry = None
        self.status = None
        self.update_status(SpotifyStatus.STOPPED)
        self.last_notification_success = False
        self.last_notification_attempt = 0
    
    def start_from_cache(self):
        return self.start_process(from_cache=True, access_token=None)
    
    def start_with_access_token(self, access_token):
        self.access_token = access_token
        self.access_token_expiry = time.time() + ACCESS_TOKEN_CACHE_SECONDS
        return self.start_process(from_cache=False, access_token=access_token)
    
    def start_process(self, from_cache=True, access_token=None):
        self.stop_process()
        self.terminated = False

        print(f"{LOG_PREFIX} Starting Spotify")

        if not from_cache and access_token:
            command = f"{COMMAND_START_WITH_ACCESS_TOKEN} {access_token}"
            print(f"{LOG_PREFIX} Starting Spotify with new access token")
        elif self.access_token and time.time() < self.access_token_expiry:
            command = f"{COMMAND_START_WITH_ACCESS_TOKEN} {self.access_token}"
            print(f"{LOG_PREFIX} Starting Spotify with cached access token")
        elif from_cache:
            command = COMMAND_START_FROM_CACHE
            print(f"{LOG_PREFIX} Starting Spotify with cached credentials")
        else:
            print(f"{LOG_PREFIX} Error: Invalid parameters for starting Spotify")
            return False

        try:
            self.process = subprocess.Popen(
                command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
        except Exception as e:
            print(f"{LOG_PREFIX} Failed to start Spotify process: {e}")
            self.update_status(SpotifyStatus.ERROR)
            return self.retry()

        if self.process.poll() is not None:
            print(f"{LOG_PREFIX} Spotify process failed to start. Return code: {self.process.returncode}")
            self.update_status(SpotifyStatus.ERROR)
            return self.retry()
        
        self.update_status(SpotifyStatus.STARTING)

        # Start monitoring the output
        self.monitor_thread = threading.Thread(target=self.monitor_output)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        # Start monitoring process status in a separate thread
        self.status_thread = threading.Thread(target=self.monitor_process_status)
        self.status_thread.daemon = True
        self.status_thread.start()

        # wait for auth success up to 5 seconds, then retry if not successful
        start_time = time.time()
        while self.status == SpotifyStatus.STARTING:
            if time.time() - start_time > 5:
                print(f"{LOG_PREFIX} Timeout waiting for authentication success")
                self.update_status(SpotifyStatus.NEEDS_AUTH)
                return self.retry()
            time.sleep(0.1)
        
        if self.status == SpotifyStatus.RUNNING:
            print(f"{LOG_PREFIX} Spotify process started successfully")
            self.retry_times = deque(maxlen=MAX_RETRIES)
            return True
        else:
            print(f"{LOG_PREFIX} Spotify process failed to start")
            return False
        
    def monitor_output(self):
        try:
            while self.process.poll() is None:
                try:
                    line = self.process.stdout.readline()
                    if line:
                        if self.status == SpotifyStatus.STARTING and STDOUT_AUTH_SUCCESS in line:
                            self.update_status(SpotifyStatus.RUNNING)
                        elif not any(ignore_str in line for ignore_str in STDOUT_IGNORE_LIST):
                            print(f"{LOG_PREFIX_LIBRESPOT} {line.strip()}")
                            if "ERROR" in line:
                                self.handle_error(line)
                    else:
                        print("No output")
                except Exception as e:
                    print(f"{LOG_PREFIX} Error reading output: {e}")
                    time.sleep(0.1)
        except Exception as e:
            print(f"{LOG_PREFIX} Error in monitor_output: {e}")
        finally:
            print(f"{LOG_PREFIX} Spotify output monitoring stopped")

    def monitor_process_status(self):
        print(f"{LOG_PREFIX} Monitoring Spotify process status")
        while self.process is not None:
            if self.process.poll() is not None:  # If the process has terminated
                self.update_status(SpotifyStatus.STOPPED)
                if self.terminated:
                    print(f"{LOG_PREFIX} Process was terminated by user. Stopping monitor.")
                    break
                else:
                    print(f"{LOG_PREFIX} Process has terminated. Attempting to restart...")
                    if not self.retry():
                        self.update_status(SpotifyStatus.ERROR)
                    print(f"{LOG_PREFIX} Failed to restart process. Stopping monitor.")
                    break
            if not self.last_notification_success and time.time() - self.last_notification_attempt > STATUS_NOTIFICATION_RETRY_INTERVAL_SECONDS:
                print(f"{LOG_PREFIX} Retrying failed status notification")
                self.notify_status()
            time.sleep(1)
        print(f"{LOG_PREFIX} Spotify process status monitoring stopped")

    def handle_error(self, error_message):
        print(f"{LOG_PREFIX} Error Detected: {error_message.strip()}")
        if self.retry():
            print(f"{LOG_PREFIX} Successfully restarted process after error.")
        else:
            print(f"{LOG_PREFIX} Failed to restart process after error.")

    def can_retry(self):
        if self.terminated:
            return False
        now = time.time()
        self.retry_times = deque([t for t in self.retry_times if now - t <= RETRY_WINDOW_SECONDS], maxlen=MAX_RETRIES)
        
        if len(self.retry_times) < MAX_RETRIES:
            self.retry_times.append(now)
            return True
        print(f"{LOG_PREFIX} Max retries reached.")
        return False

    def retry(self):
        if self.can_retry():
            print(f"{LOG_PREFIX} Attempting to restart...")
            self.stop_process()
            if self.start_from_cache():
                print(f"{LOG_PREFIX} Successfully restarted process.")
                return True
            else:
                print(f"{LOG_PREFIX} Failed to restart process.")
        else:
            print(f"{LOG_PREFIX} Not attempting to restart.")
        return False

    def stop_process(self):
        if self.process:
            self.terminated = True
            self.process.terminate()
            self.process.wait()

    def get_status(self):
        return self.status.value
    
    def update_status(self, status):
        if status not in SpotifyStatus:
            print(f"{LOG_PREFIX} Invalid status: {status}")
            raise ValueError(f"Invalid status: {status}")
        prev_status = self.status
        self.status = status
        if prev_status != status:
            print(f"{LOG_PREFIX} Spotify status updated to {status.value}")
            self.notify_status()
    
    def notify_status(self):
        self.last_notification_success = False
        self.last_notification_attempt = time.time()
        try:
            response = requests.post('http://island:80/wave/status', json={'status': self.status.value}, timeout=5)
            if response.status_code == 200:
                self.last_notification_success = True
                print(f"{LOG_PREFIX} Successfully sent status notification")
            else:
                raise Exception(f"HTTP {response.status_code}")
        except Exception as e:
            print(f"{LOG_PREFIX} Error sending status notification: {e}")