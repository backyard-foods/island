import subprocess
import os
import requests

def capture_image_to_memory():
    try:
        result = subprocess.run(["libcamera-jpeg", "-n", "-o", "-"], capture_output=True, check=True)
        image_data = result.stdout
        print("Image captured to memory")
        return image_data
    except subprocess.CalledProcessError as e:
        print(f"Error capturing image: {e}")
        return None

def upload_image(image_data, bearer_token):
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

def capture_and_upload(bearer_token):
    image_data = capture_image_to_memory()
    if image_data:
        return upload_image(image_data, bearer_token)
    else:
        print("Image capture failed. No data to upload.")
        return False
