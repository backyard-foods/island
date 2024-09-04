from flask import Flask, render_template, jsonify, request
from printer_manager import PrinterManager
import threading

app = Flask(__name__, template_folder='../views', static_folder='../views/public')
printer_manager = PrinterManager()

@app.route('/')
def hello_world():
    return render_template('index.html')

@app.route('/receipt/status')
def get_printer_status():
    return jsonify({"status": printer_manager.get_status()})

@app.route('/receipt/print', methods=['POST'])
def trigger_print_job():
    data = request.json
    # Assume the print data is sent in the request body
    success = printer_manager.print(data.get('content', ''))
    return jsonify({"success": success})

@app.route('/test')
def print():
    return "printing!"

if __name__ == '__main__':
    # Start the printer status checking in a separate thread
    threading.Thread(target=printer_manager.start_status_checking, daemon=True).start()
    app.run(host='0.0.0.0', port=80)
