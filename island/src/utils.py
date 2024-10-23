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


def restart_container():
    app_id = os.environ['BALENA_APP_ID']
    supervisor_address = os.environ['BALENA_SUPERVISOR_ADDRESS']
    api_key = os.environ['BALENA_SUPERVISOR_API_KEY']
    restart_policy = os.environ['RESTART_POLICY']

    if not all([app_id, supervisor_address, api_key, restart_policy]):
        print("Error: Missing required environment variables")
        return

    if restart_policy == "1":
        print("Restarting container")
    else:
        print("Skipping restart per policy")
        return

    url = f"{supervisor_address}/v1/restart?apikey={api_key}"
    payload = {"appId": app_id}
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Container restart request sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Failed to restart container: {e}")

def format_string(string, double_size, flip=False):
    char_limit = 21 if double_size else 38
    lines = []
    
    # Split the input string by newlines first
    for input_line in string.split('\n'):
        words = input_line.split()
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= char_limit:
                current_line += " " + word if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
    
    if flip:
        lines.reverse()
    return '\n'.join(lines)
