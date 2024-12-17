from flask import Flask, jsonify, request
import threading
from byf_api_client import BYFAPIClient
from utils import restart_service, start_service, stop_service
import requests

app = Flask(__name__)

byf_client = BYFAPIClient()

def capture_image(trigger):
    try:
        print(f"Sending capture request to baywatch with trigger: {trigger}")
        token = byf_client.get_access_token()
        response = requests.get(f'http://baywatch:1234/capture?token={token}&trigger={trigger}')
        response.raise_for_status()
        return {"success": True, "message": "Image capture request sent"}
    except requests.RequestException as e:
        print(f"Error capturing image: {str(e)}")
        return {"success": False, "message": "Error capturing image"}

def detect_image(trigger):
    print(f"Sending detect request to baywatch with trigger: {trigger}")
    token = byf_client.get_access_token()
    response = requests.get(f'http://baywatch:1234/detect?token={token}&trigger={trigger}')
    return response
    
@app.route('/receipt/status')
def get_receipt_printer_status():
    try:
        response = requests.get('http://receipt-printer:1234/status')
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        print(f"Error getting receipt printer status: {str(e)}")
        return jsonify({"status": "service_offline"})
    
@app.route('/receipt/configure')
def configure_receipt_printer():
    fast = request.args.get('fast', 'false')
    high_density = request.args.get('high_density', 'true')
    success = requests.get(f'http://receipt-printer:1234/configure?fast={fast}&high_density={high_density}').json().get('success', False)
    restart_service("receipt-printer")
    return jsonify({"success": success})

def print_receipt_async(order, upcs, details, message, wait):
    try:
        success = requests.get(f'http://receipt-printer:1234/print?order={order}&upcs={upcs}&details={details}&message={message}&wait={wait}').json().get('success', False)
        print(f"Receipt print success: {success}")
        if success:
            byf_client.notify_print_success(order)
        return success
    except Exception as e:
        print(f"Error printing receipt: {str(e)}")
        return False


@app.route('/receipt/print')
def print_receipt():
    image_error = False
    image_capture = 'trigger' in request.args
    if image_capture:
        try:
            if request.args.get('image') == 'true':
                capture_image(request.args.get('trigger'))
            if request.args.get('detect') == 'true':
                detect_image(request.args.get('trigger')) 
        except Exception as e:
            image_error = True
            print(f"Error capturing image: {str(e)}")
        
    
    order = request.args.get('order', '')
    message = request.args.get('message', '')
    upcs = request.args.get('upcs', [])
    details = request.args.get('details', '')
    wait = request.args.get('wait', None)
    
    threading.Thread(target=print_receipt_async, args=(order, upcs, details, message, wait), daemon=True).start()
    
    if image_capture:
        return jsonify({"success": True, "message": "Receipt print job started", "image_error": image_error})
    else:
        return jsonify({"success": True, "message": "Receipt print job started"})

@app.route('/receipt/reload')
def reload_receipt_paper():
    try:
        success = requests.get('http://receipt-printer:1234/reload').json().get('success', False)
        return jsonify({"success": success})
    except requests.RequestException as e:
        print(f"Error sending receipt printer reload request: {str(e)}")
        return jsonify({"success": False})

@app.route('/label/status')
def get_label_printer_status():
    try:
        response = requests.get('http://label-printer:1234/status')
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        print(f"Error getting label printer status: {str(e)}")
        return jsonify({"status": "service_offline"})

@app.route('/label/configure')
def configure_label_printer():
    buzzer = request.args.get('buzzer', 'false')
    paper_removal_standby = request.args.get('paper_removal_standby', 'false')
    success = requests.get(f'http://label-printer:1234/configure?buzzer={buzzer}&paper_removal_standby={paper_removal_standby}').json().get('success', False)
    restart_service("label-printer")
    return jsonify({"success": success})

def print_label_async(order, item, upcs, item_number, item_total, fulfillment, paid):
    try:
        success = requests.get(f'http://label-printer:1234/print?order={order}&item={item}&upcs={upcs}&item_number={item_number}&item_total={item_total}&fulfillment={fulfillment}&paid={paid}').json().get('success', False)
        print(f"Label print success: {success}")
        if fulfillment and success:
            byf_client.notify_label_success(fulfillment)
        return success
    except Exception as e:
        print(f"Error printing label: {str(e)}")
        return False

@app.route('/label/print')
def print_label():
    image_error = False
    image_capture = 'trigger' in request.args
    if image_capture:
        try:
            if request.args.get('image') == 'true':
                capture_image(request.args.get('trigger'))
            if request.args.get('detect') == 'true':
                detect_image(request.args.get('trigger'))
        except Exception as e:
            image_error = True
            print(f"Error capturing image: {str(e)}")

    order = request.args.get('order', '')
    item = request.args.get('item', '')
    upcs = request.args.get('upcs', [])
    item_number = request.args.get('item_number', '')
    item_total = request.args.get('item_total', '')
    fulfillment = request.args.get('fulfillment', '')
    paid = request.args.get('paid', 'false')

    threading.Thread(target=print_label_async, args=(order, item, upcs, item_number, item_total, fulfillment, paid), daemon=True).start()
    
    if image_capture:
        return jsonify({"success": True, "message": "Label print job started", "image_error": image_error})
    else:
        return jsonify({"success": True, "message": "Label print job started"})

@app.route('/label/print_text')
def print_text():
    text = request.args.get('text')
    try:
        success = requests.get(f'http://label-printer:1234/print_text?text={text}').json().get('success', False)
        return jsonify({"success": success})
    except requests.RequestException as e:
        print(f"Error sending label printer text print request: {str(e)}")
        return jsonify({"success": False})

@app.route('/label/reload')
def reload_label_paper():
    try:
        success = requests.get('http://label-printer:1234/reload').json().get('success', False)
        return jsonify({"success": success})
    except requests.RequestException as e:
        print(f"Error sending label printer reload request: {str(e)}")
        return jsonify({"success": False})

@app.route('/image/capture')
def capture():
    trigger = request.args.get('trigger', '')
    result = capture_image(trigger)
    return jsonify(result)

@app.route('/image/detect')
def detect():
    trigger = request.args.get('trigger', '')
    response = detect_image(trigger)
    if response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify(response.json()), response.status_code

@app.route('/light')
def light_control():
    on = request.args.get('on', '').lower() == 'true'
    state = 'on' if on else 'off'

    try:
        print(f"Sending light {state} request to porchlight")
        response = requests.get(f'http://porchlight:1234/{state}')
        response.raise_for_status()
        return jsonify({"success": True, "message": response.json().get('message', 'Light state changed')})
    except requests.RequestException as e:
        print(f"Error sending light {state} request: {str(e)}")
        return jsonify({"success": False, "message": response.json().get('message', 'Light state changed')})
    
@app.route('/store', methods=['POST'])
def store_control():  
    open = request.args.get('open', '').lower() == 'true'
    state = 'on' if open else 'off'

    try:
        if open:
            print("Starting wave from store control")
            start_service('wave')
        else:
            print("Stopping wave from store control")
            stop_service('wave')
        print(f"Sending light {state} request to porchlight")
        response = requests.get(f'http://porchlight:1234/{state}')
        response.raise_for_status()
        return jsonify({"success": True})
    except requests.RequestException as e:
        print(f"Error sending light {state} request: {str(e)}")
        return jsonify({"success": False})

@app.route('/wave/auth', methods=['POST'])
def wave_auth():
    data = request.json
    print(f"Received wave auth request: {data}")
    access_token = data.get('access_token')
    print(f"Received access token: {access_token}")
    if not access_token:
        return jsonify({"success": False, "message": "Access token is required"}), 400
    try:
        result = requests.post('http://wave:1234/auth', json={'access_token': access_token}, timeout=5)
        result.raise_for_status() 
        return jsonify({"success": result.json().get('success', False), "message": result.json().get('message', 'Authentication completed')})
    except requests.exceptions.RequestException as e:
        print(f"Error during Wave authentication: {str(e)}")
        return jsonify({"success": False, "message": f"Wave authentication failed: {str(e)}"}), 500

@app.route('/wave/status', methods=['GET', 'POST'])
def wave_status():
    if request.method == 'GET':
        try:
            response = requests.get('http://wave:1234/status')
            response.raise_for_status()
            return jsonify({"status": response.json().get('status', ''), "success": True})
        except requests.RequestException as e:
            print(f"Error getting wave status: {str(e)}")
            return jsonify({"status": "error", "message": "Failed to get wave status", "success": False}), 500
    elif request.method == 'POST':
        data = request.json
        status = data.get('status')
        if not status:
            return jsonify({"success": False, "message": "Status is required"}), 400
        success = byf_client.notify_wave_status(status)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False}), 500
        
@app.route('/wave', methods=['POST'])
def wave_control():
    on = request.args.get('on', '').lower() == 'true'

    try:
        if on:
            print("Starting wave from wave control")
            start_service('wave')
        else:
            print("Stopping wave from wave control")
            stop_service('wave')
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error controlling wave: {str(e)}")
        return jsonify({"success": False})

if __name__ == '__main__':
    threading.Thread(target=byf_client.start_polling, daemon=True).start()
    
    app.run(host='0.0.0.0', port=80)
