import os
import requests
import time
from picamera2 import Picamera2
import threading
import io

LOG_PREFIX = "[camera]"
COOLDOWN = 0.25

class CameraManager:
    def __init__(self):
        try:
            self.camera = Picamera2()
        except Exception as e:
            self.runtime_error(f"Fatal error: Failed to initialize camera: {e}")
        self.cooldown = COOLDOWN
        self.last_request_time = 0
        self.lock = threading.Lock()

    def capture_image_to_memory(self):
        with self.lock:
            self.throttle()
            try:
                data = io.BytesIO()
                self.camera.start()
                self.camera.capture_file(data, format="jpeg")
                return data.getvalue()
            except Exception as e:
                print(f"Error capturing image: {e}")
                if "Failed to start camera" in str(e):
                    self.runtime_error("Failed to start camera")
                return None
    
    def throttle(self):
        current_time = time.time()
        elapsed_time = current_time - self.last_request_time
        if elapsed_time < self.cooldown:
            time.sleep(self.cooldown - elapsed_time)
            print(f"{LOG_PREFIX} Throttled for {self.cooldown - elapsed_time} seconds")
        self.last_request_time = time.time()

    def upload_image(self, image_data, bearer_token):
        base_url = os.environ['BYF_API_URL']
        url = f"{base_url}/functions/v1/image"
        
        try:
            files = {'file': ('image.jpeg', image_data, 'image/jpeg')}
            headers = {"Authorization": f"Bearer {bearer_token}"}
            response = requests.post(url, files=files, headers=headers)
            response.raise_for_status()
            print("Image uploaded successfully.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error uploading image: {e}")
            return False

    def capture_and_upload(self, bearer_token):
        image_data = self.capture_image_to_memory()
        if image_data:
            return self.upload_image(image_data, bearer_token)
        else:
            print("Image capture failed. No data to upload.")
            return False
        
    def runtime_error(self, message):
        print(f"Runtime error: {message}")
        time.sleep(10)
        raise RuntimeError(message)

    def close(self):
        self.camera.close()
