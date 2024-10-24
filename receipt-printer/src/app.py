from flask import Flask, jsonify, request
from receipt_printer_manager import ReceiptPrinterManager
import threading
import requests
import time

RECEIPT_DEBUG_MODE = False

app = Flask(__name__)
receipt_printer_manager = ReceiptPrinterManager()

@app.route('/status')
def get_receipt_printer_status():
    try:
        return jsonify(receipt_printer_manager.get_status())
    except Exception as e:
        return jsonify({"status": "unknown", "reason": f"exception: {str(e)}"})

@app.route('/configure')
def configure_receipt_printer():
    fast = request.args.get('fast', 'false') == 'true'
    high_density = request.args.get('high_density', 'true') == 'true'
    success = receipt_printer_manager.configure_printer(fast, high_density)
    return jsonify({"success": success})

@app.route('/print')
def print_receipt():
    order = request.args.get('order', '')
    message = request.args.get('message', '')
    upcs = request.args.get('upcs', [])
    details = request.args.get('details', '')
    wait = request.args.get('wait', None)

    success = receipt_printer_manager.print_receipt(order, upcs, details, message, wait)
    return jsonify({"success": success})

@app.route('/reload')
def reload_receipt_paper():
    success = receipt_printer_manager.reload_paper()
    return jsonify({"success": success})

def send_receipt_debug_request():
    time.sleep(5)
    print("[RECEIPT_DEBUG_MODE] Sending debug print request...")
    try:
        response = requests.get('http://receipt-printer:1234/print?order=Debug+Order&wait=30&upcs=%5B860012979325%2C860012979332%5D&details=6+Tender+Combo+-+%2412.99%0AJust+Fries+-+%242.99%0ATOTAL+-+%2415.98&image=true&trigger=order-created&message=Park+fact%3A+Channel+Islands+has+10%25+of+the+park%27s+species+found+nowhere+else+on+Earth')
        response.raise_for_status()
        print("[RECEIPT_DEBUG_MODE] Debug print request sent successfully")
    except requests.RequestException as e:
        print(f"[RECEIPT_DEBUG_MODE] Error sending debug print request: {str(e)}")

if __name__ == '__main__':
    if RECEIPT_DEBUG_MODE:
        threading.Thread(target=send_receipt_debug_request, daemon=True).start()
    
    app.run(host='0.0.0.0', port=1234)
