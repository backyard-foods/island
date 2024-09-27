import os
import requests
import time
from picamera2 import Picamera2
import threading
import io
import cv2

LOG_PREFIX = "[camera]"
COOLDOWN = 0.25
DETECTION_INTERVAL = 30

class CameraManager:
    def __init__(self):
        try:
            self.camera = Picamera2()
            self.camera.stop()
            self.camera.configure(self.camera.create_preview_configuration(main={"format": 'XRGB8888', "size": (2304, 1296)}))
        except Exception as e:
            self.runtime_error(f"Fatal error: Failed to initialize camera: {e}")
        self.cooldown = COOLDOWN
        self.last_request_time = 0
        self.last_detection_time = 0
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
            finally:
                self.camera.stop()
    
    def throttle(self):
        current_time = time.time()
        elapsed_time = current_time - self.last_request_time
        if elapsed_time < self.cooldown:
            time.sleep(self.cooldown - elapsed_time)
            print(f"{LOG_PREFIX} Throttled for {self.cooldown - elapsed_time} seconds")
        self.last_request_time = time.time()

    def upload_image(self, image_data, bearer_token, trigger="",):
        base_url = os.environ['BYF_API_URL']
        url = f"{base_url}/functions/v1/image"
        
        try:
            files = {'file': ('image.jpeg', image_data, 'image/jpeg')}
            data = {'trigger': trigger}
            headers = {"Authorization": f"Bearer {bearer_token}"}
            response = requests.post(url, files=files, data=data, headers=headers)
            response.raise_for_status()
            print("Image uploaded successfully.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error uploading image: {e}")
            return False

    def capture_and_upload(self, bearer_token, trigger=""):
        image_data = self.capture_image_to_memory()
        if image_data:
            return self.upload_image(image_data, bearer_token, trigger=trigger)
        else:
            print("Image capture failed. No data to upload.")
            return False
        
    def runtime_error(self, message):
        print(f"Runtime error: {message}")
        time.sleep(10)
        raise Exception(message)
    
    def detection_thread(self, bearer_token, face_detector, trigger=""):
        with self.lock:
            self.throttle()
            self.camera.start()

            start_time = time.time()
            print("Starting detection")
            face_detected = False
            while time.time() - start_time < DETECTION_INTERVAL and not face_detected:  # Run for 30 seconds or until a face is detected
                im = self.camera.capture_array()

                grey = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
                try:
                    faces = face_detector.detectMultiScale(grey, 1.1, 5)
                    if len(faces) > 0:
                        print(f"Found {len(faces)} objects")
                        face_detected = True
                    else:
                        print("No objects detected")
                except cv2.error as e:
                    print(f"OpenCV error during face detection: {e}")
                    break

                for (x, y, w, h) in faces:
                    cv2.rectangle(im, (x, y), (x + w, y + h), (0, 255, 0))

                time.sleep(0.001)

            self.camera.stop()

        if face_detected:
            print("Object detected! Exiting test.")
            # Capture the image and upload it
            image_data = cv2.imencode('.jpg', im)[1].tobytes()
            self.upload_image(image_data, bearer_token, trigger=trigger)
        else:
            print("Test completed without detecting an object.")

    def detect_and_upload(self, bearer_token, trigger=""):
        if (self.last_detection_time + DETECTION_INTERVAL) > time.time():
            print("Detection already in progress")
            return {"success": False, "message": "Detection already in progress"}

        cascade_path = "src/haarcascade_frontalface_default.xml"

        # Check if the file exists
        if not os.path.isfile(cascade_path):
            print(f"Error: Cascade file not found at {cascade_path}")
            return {"success": False, "message": "Cascade file not found"}

        face_detector = cv2.CascadeClassifier(cascade_path)
        
        # Check if the classifier is empty
        if face_detector.empty():
            print("Error: Failed to load cascade classifier")
            return {"success": False, "message": "Failed to load cascade classifier"}
        
        self.last_detection_time = time.time()
        threading.Thread(target=self.detection_thread, args=(bearer_token, face_detector, trigger), daemon=True).start()
        return {"success": True, "message": "Detection started"}


    def close(self):
        self.camera.close()
