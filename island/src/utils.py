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