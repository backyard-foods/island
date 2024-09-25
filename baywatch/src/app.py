from flask import Flask, jsonify, request
from camera_manager import capture_and_upload

app = Flask(__name__)

@app.route('/capture')
def capture():
    token = request.args.get('token')
    if not token:
        return jsonify({"success": False, "message": "Token is required"}), 400
    
    print("Capturing image")
    if capture_and_upload(token):
        return jsonify({"success": True, "message": "Image captured"})
    else:
        return jsonify({"success": False, "message": "Image capture failed"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1234)