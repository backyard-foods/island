from flask import Flask, render_template, jsonify, request
from receipt_printer_manager import ReceiptPrinterManager
import threading

app = Flask(__name__, template_folder='../views', static_folder='../views/public')
receipt_printer_manager = ReceiptPrinterManager()

@app.route('/receipt/status')
def get_printer_status():
    return jsonify({"status": receipt_printer_manager.get_status()})

@app.route('/receipt/print')
def trigger_print_job():
    order_number = request.args.get('order_number', '00')
    success = receipt_printer_manager.print(order_number, 1)
    return jsonify({"success": success})

@app.route('/receipt/reload')
def reload_paper():
    success = receipt_printer_manager.reload_paper()
    return jsonify({"success": success})

@app.route('/test')
def print():
    return "printing!"

if __name__ == '__main__':
    # Start the printer status checking in a separate thread
    threading.Thread(target=receipt_printer_manager.start_status_checking, daemon=True).start()
    app.run(host='0.0.0.0', port=80)
