from flask import Flask, jsonify, request
from src.reaper import Reaper

app = Flask(__name__)
reaper = Reaper()

@app.route('/keepalive')
def keepalive():
    if reaper.keepalive():
        return jsonify({"success": True, "message": "Keepalive sent"})
    else:
        print("Keepalive failed")
        return jsonify({"success": False, "message": "Keepalive failed"})

@app.route('/reboot')
def reboot():
    reaper.reboot()
    return jsonify({"success": True, "message": "Rebooting device"})

if __name__ == '__main__':
    with reaper:
        app.run(host='0.0.0.0', port=1234)