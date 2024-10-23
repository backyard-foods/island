from flask import Flask, jsonify, request
from label_printer_manager import LabelPrinterManager
import threading
import requests
import time

LABEL_DEBUG_MODE = False

app = Flask(__name__)
label_printer_manager = LabelPrinterManager()

@app.route('/status')
def get_label_printer_status():
    try:
        return jsonify(label_printer_manager.get_status())
    except Exception as e:
        return jsonify({"status": "unknown", "reason": f"exception: {str(e)}"})

@app.route('/configure')
def configure_label_printer():
    buzzer = request.args.get('buzzer', 'false') == 'true'
    paper_removal_standby = request.args.get('paper_removal_standby', 'false') == 'true'
    success = label_printer_manager.configure_printer(buzzer, paper_removal_standby)
    return jsonify({"success": success})

@app.route('/print')
def print_label():
    order = request.args.get('order', '')
    item = request.args.get('item', '')
    upc = request.args.get('upc', '')
    item_number = request.args.get('item_number', '')
    item_total = request.args.get('item_total', '')
    fulfillment = request.args.get('fulfillment')

    success = label_printer_manager.print_label(order, item, upc, item_number, item_total, fulfillment)
    return jsonify({"success": success})

@app.route('/print_text')
def print_text():
    text = request.args.get('text')
    success = label_printer_manager.print_text(text)
    return jsonify({"success": success})

@app.route('/reload')
def reload_label_paper():
    success = label_printer_manager.reload_paper()
    return jsonify({"success": success})

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
    if LABEL_DEBUG_MODE:
        threading.Thread(target=send_label_debug_request, daemon=True).start()
    
    app.run(host='0.0.0.0', port=1234)
