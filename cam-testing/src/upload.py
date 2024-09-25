import sys
import requests
from pathlib import Path

def upload_file(filename):
    # Construct the URL
    base_url = "http://192.168.1.86:54321/storage/v1/object/test"
    url = f"{base_url}/{filename}"
    bearer_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIxODVmMmY4My1kNjNhLTRjOWItYjRhMC03ZTRhODg1Nzk5ZTIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzI3MjEzMDc2LCJpYXQiOjE3MjcyMDk0NzYsImVtYWlsIjoibWlsYW5AYmFja3lhcmRmb29kcy5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7fSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTcyNzIwOTQ3Nn1dLCJzZXNzaW9uX2lkIjoiZGM2ZDE1YTAtZjFhMi00NjRlLWFhMzQtYzVmYTdhYTBmNmNlIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.V5ogETP2A9KUEsXO79ysayoCuLK3bDX7dAficM5d7h4"

    # Check if the file exists
    file_path = Path(filename)
    if not file_path.is_file():
        print(f"Error: File '{filename}' not found.")
        return

    # Open and read the file
    with open(file_path, 'rb') as file:
        file_data = file.read()

    # Send the POST request
    try:
        response = requests.post(url, data=file_data, headers={"Authorization": bearer_token})
        response.raise_for_status()  # Raise an exception for bad status codes
        print(f"File '{filename}' uploaded successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error uploading file: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python upload.py <filename>")
    else:
        filename = sys.argv[1]
        upload_file(filename)
