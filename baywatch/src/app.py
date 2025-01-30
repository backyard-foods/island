from flask import Flask, jsonify, request
from camera_manager import CameraManager

app = Flask(__name__)

camera_manager = CameraManager()

@app.route('/capture')
def capture():
    token = request.args.get('token')
    trigger = request.args.get('trigger', '')
    if not token:
        return jsonify({"success": False, "message": "Token is required"}), 400
    
    print("Capturing image")
    if camera_manager.capture_and_upload(token, trigger):
        return jsonify({"success": True, "message": "Capture started"})
    else:
        return jsonify({"success": False, "message": "Capture failed"}), 500
    
@app.route('/record')
def record():
    token = request.args.get('token')
    trigger = request.args.get('trigger', '')
    if not token:
        return jsonify({"success": False, "message": "Token is required"}), 400
    
    print("Recording clip")
    if camera_manager.record_and_upload(token, trigger):
        return jsonify({"success": True, "message": "Recording started"})
    else:
        return jsonify({"success": False, "message": "Recording failed"}), 500
    
@app.route('/detect')
def detect():
    token = request.args.get('token')
    trigger = request.args.get('trigger', '')
    if not token:
        return jsonify({"success": False, "message": "Token is required"}), 400
    
    print("Detecting object")
    result = camera_manager.detect_and_upload(token, trigger)
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify(result), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1234)