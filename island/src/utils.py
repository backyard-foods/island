import os
import requests

def restart_service(service_name):
    print(f"Restarting {service_name} service")
    app_id = os.environ['BALENA_APP_ID']
    supervisor_address = os.environ['BALENA_SUPERVISOR_ADDRESS']
    api_key = os.environ['BALENA_SUPERVISOR_API_KEY']

    if not all([app_id, supervisor_address, api_key]):
        print("Error: Missing required environment variables")
        return

    url = f"{supervisor_address}/v2/applications/{app_id}/restart-service?apikey={api_key}"
    payload = {"serviceName": service_name}
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"{service_name} restart request sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Failed to restart {service_name}: {e}")

def stop_service(service_name):
    print(f"Stopping {service_name} service")
    app_id = os.environ['BALENA_APP_ID']
    supervisor_address = os.environ['BALENA_SUPERVISOR_ADDRESS']
    api_key = os.environ['BALENA_SUPERVISOR_API_KEY']

    if not all([app_id, supervisor_address, api_key]):
        print("Error: Missing required environment variables")
        return

    url = f"{supervisor_address}/v2/applications/{app_id}/stop-service?apikey={api_key}"
    payload = {"serviceName": service_name}
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"{service_name} stop request sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Failed to stop {service_name}: {e}")

def start_service(service_name):
    print(f"Starting {service_name} service")
    app_id = os.environ['BALENA_APP_ID']
    supervisor_address = os.environ['BALENA_SUPERVISOR_ADDRESS']
    api_key = os.environ['BALENA_SUPERVISOR_API_KEY']

    if not all([app_id, supervisor_address, api_key]):
        print("Error: Missing required environment variables")
        return

    url = f"{supervisor_address}/v2/applications/{app_id}/start-service?apikey={api_key}"
    payload = {"serviceName": service_name}
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"{service_name} start request sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Failed to start {service_name}: {e}")

def get_service_status(service_name):
    app_id = os.environ['BALENA_APP_ID']
    supervisor_address = os.environ['BALENA_SUPERVISOR_ADDRESS']
    api_key = os.environ['BALENA_SUPERVISOR_API_KEY']

    if not all([app_id, supervisor_address, api_key]):
        print("Error: Missing required environment variables")
        return

    url = f"{supervisor_address}/v2/applications/state?apikey={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        service_status = data.get(os.environ['BALENA_APP_NAME'], {}).get('services', {}).get(service_name, {}).get('status')
        
        if service_status:
            return service_status
        else:
            print(f"Service {service_name} not found")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Failed to get {service_name} status: {e}")
        return None