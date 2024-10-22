from flask import Flask, jsonify, request
from receipt_printer_manager import ReceiptPrinterManager
from label_printer_manager import LabelPrinterManager
import threading
from byf_api_client import BYFAPIClient
import requests
import time

RECEIPT_DEBUG_MODE = False
LABEL_DEBUG_MODE = False

app = Flask(__name__)
byf_client = BYFAPIClient()
receipt_printer_manager = ReceiptPrinterManager(byf_client)
#label_printer_manager = LabelPrinterManager(byf_client)

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
    return jsonify({"status": receipt_printer_manager.get_status()})

@app.route('/receipt/print')
def print_receipt():
    order = request.args.get('order', '00')
    message = request.args.get('message', '')
    upcs = request.args.get('upcs', [])
    details = request.args.get('details', '3 Tender Combo')
    wait = request.args.get('wait', None)
    
    # Start the print job in a separate thread
    threading.Thread(target=receipt_printer_manager.print_receipt, args=(order, upcs, details, message, wait), daemon=True).start()
    
    if 'trigger' in request.args:
        if request.args.get('image') == 'true':
            capture_image(request.args.get('trigger'))
        if request.args.get('detect') == 'true':
            detect_image(request.args.get('trigger'))
    
    return jsonify({"success": True, "message": "Receipt print job started"})

@app.route('/receipt/reload')
def reload_receipt_paper():
    success = receipt_printer_manager.reload_paper()
    return jsonify({"success": success})

@app.route('/label/status')
def get_label_printer_status():
    try:
        response = requests.get('http://label-printer:1234/status')
        response.raise_for_status()
        return jsonify({"status": response.json().get('status', '')})
    except requests.RequestException as e:
        print(f"Error getting label printer status: {str(e)}")
        return jsonify({"status": "service_offline"})

@app.route('/label/configure')
def configure_label_printer():
    buzzer = request.args.get('buzzer', 'false')
    paper_removal_standby = request.args.get('paper_removal_standby', 'false')
    try:
        response = requests.get(f'http://label-printer:1234/configure?buzzer={buzzer}&paper_removal_standby={paper_removal_standby}')
        response.raise_for_status()
        return jsonify({"success": True, "message": "Label printer configure request sent"})
    except requests.RequestException as e:
        print(f"Error sending label printer configure request: {str(e)}")
        return jsonify({"success": False, "message": "Error sending label printer configure request"})

def print_label_async(order, item, upc, item_number, item_total, fulfillment):
    try:
        success = requests.get(f'http://label-printer:1234/print?order={order}&item={item}&upc={upc}&item_number={item_number}&item_total={item_total}&fulfillment={fulfillment}').json().get('success', False)
        print(f"Label print success: {success}")
        if fulfillment and success:
            byf_client.notify_label_success(fulfillment)
        return success
    except Exception as e:
        print(f"Error printing label: {str(e)}")
        return False

@app.route('/label/print')
def print_label():
    if 'trigger' in request.args:
        if request.args.get('image') == 'true':
            capture_image(request.args.get('trigger'))
        if request.args.get('detect') == 'true':
            detect_image(request.args.get('trigger'))

    order = request.args.get('order', '')
    item = request.args.get('item', '')
    upc = request.args.get('upc', '')
    item_number = request.args.get('item_number', '')
    item_total = request.args.get('item_total', '')
    fulfillment = request.args.get('fulfillment', '')

    threading.Thread(target=print_label_async, args=(order, item, upc, item_number, item_total, fulfillment), daemon=True).start()
    
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
        print(f"Sending light {state} request to porchlight")
        response = requests.get(f'http://porchlight:1234/{state}')
        response.raise_for_status()
        return jsonify({"success": True, "message": response.json().get('message', 'Light state changed')})
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
        result.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
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

def send_receipt_debug_request():
    time.sleep(5)
    print("[RECEIPT_DEBUG_MODE] Sending debug print request...")
    try:
        response = requests.get('http://localhost/receipt/print?order=Debug+Order&wait=30&upcs=%5B860012979325%2C860012979332%5D&details=6+Tender+Combo+-+%2412.99%0AJust+Fries+-+%242.99%0ATOTAL+-+%2415.98&image=true&trigger=order-created&message=Park+fact%3A+Channel+Islands+has+10%25+of+the+park%27s+species+found+nowhere+else+on+Earth')
        response.raise_for_status()
        print("[RECEIPT_DEBUG_MODE] Debug print request sent successfully")
    except requests.RequestException as e:
        print(f"[RECEIPT_DEBUG_MODE] Error sending debug print request: {str(e)}")

def send_label_debug_request():
    time.sleep(5)
    print("[LABEL_DEBUG_MODE] Sending debug print request...")
    try:
        response = requests.get('http://localhost/label/print?order=Debug&item=3%20Tender%20Combo&upc=123456789123&item_number=1&item_total=3&fulfillment=8f50e9ec-ef4b-4695-bd04-794d6f9f477c&image=true&trigger=order-created')
        response.raise_for_status()
        print("[LABEL_DEBUG_MODE] Debug print request sent successfully")
    except requests.RequestException as e:
        print(f"[LABEL_DEBUG_MODE] Error sending debug print request: {str(e)}")

if __name__ == '__main__':
    # Start receipt & label printer status checking in a separate thread
    threading.Thread(target=receipt_printer_manager.start_status_checking, daemon=True).start()
    threading.Thread(target=byf_client.start_polling, daemon=True).start()
    
    if RECEIPT_DEBUG_MODE:
        threading.Thread(target=send_receipt_debug_request, daemon=True).start()
    #if LABEL_DEBUG_MODE:
        #threading.Thread(target=send_label_debug_request, daemon=True).start()
    
    app.run(host='0.0.0.0', port=80)
