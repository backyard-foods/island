from flask import Flask, jsonify, request
from receipt_printer_manager import ReceiptPrinterManager
from label_printer_manager import LabelPrinterManager
import threading
from byf_api_client import BYFAPIClient

app = Flask(__name__)
byf_client = BYFAPIClient()
receipt_printer_manager = ReceiptPrinterManager(byf_client)
label_printer_manager = LabelPrinterManager(byf_client)

@app.route('/receipt/status')
def get_receipt_printer_status():
    return jsonify({"status": receipt_printer_manager.get_status()})

@app.route('/label/status')
def get_label_printer_status():
    return jsonify({"status": label_printer_manager.get_status()})

@app.route('/receipt/print')
def print_receipt():
    order = request.args.get('order', '00')
    message = request.args.get('message', '')
    skus = request.args.get('skus', ['1'])
    details = request.args.get('details', '3 Tender Combo')
    # Start the print job in a separate thread
    threading.Thread(target=receipt_printer_manager.print_receipt, args=(order, skus, details, message), daemon=True).start()
    return jsonify({"success": True, "message": "Receipt print job started"})

@app.route('/label/print')
def print_label():
    order = request.args.get('order', '00')
    item = request.args.get('item', '3 Tender Combo')
    item_number = request.args.get('item_number', '1')
    item_total = request.args.get('item_total', '1')
    fulfillment = request.args.get('fulfillment')

    if fulfillment:
        threading.Thread(target=label_printer_manager.print_label, args=(order, item, item_number, item_total, fulfillment), daemon=True).start()
    else:
        threading.Thread(target=label_printer_manager.print_label, args=(order, item, item_number, item_total), daemon=True).start()
    
    return jsonify({"success": True, "message": "Label print job started"})

@app.route('/receipt/reload')
def reload_receipt_paper():
    success = receipt_printer_manager.reload_paper()
    return jsonify({"success": success})

@app.route('/label/reload')
def reload_label_paper():
    success = label_printer_manager.reload_paper()
    return jsonify({"success": success})

if __name__ == '__main__':
    # Start receipt & label printer status checking in a separate thread
    # threading.Thread(target=receipt_printer_manager.start_status_checking, daemon=True).start()
    # threading.Thread(target=label_printer_manager.start_status_checking, daemon=True).start()   
    app.run(host='0.0.0.0', port=80)
