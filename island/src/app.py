from flask import Flask, jsonify, request
from receipt_printer_manager import ReceiptPrinterManager
import threading

app = Flask(__name__)
receipt_printer_manager = ReceiptPrinterManager()

@app.route('/receipt/status')
def get_printer_status():
    return jsonify({"status": receipt_printer_manager.get_status()})

@app.route('/receipt/print')
def trigger_print_job():
    order = request.args.get('order', '00')
    message = request.args.get('message', '')
    sku = request.args.get('sku', '1')
    details = request.args.get('details', '3 Tender Combo')
    message = request.args.get('message', 'Park fact: Yellowstone was the first national park in the world, established in 1872')
    success = receipt_printer_manager.print_receipt(order, sku, details, message)
    return jsonify({"success": success})

@app.route('/receipt/reload')
def reload_paper():
    success = receipt_printer_manager.reload_paper()
    return jsonify({"success": success})

if __name__ == '__main__':
    # Start the printer status checking in a separate thread
    threading.Thread(target=receipt_printer_manager.start_status_checking, daemon=True).start()
    app.run(host='0.0.0.0', port=80)
