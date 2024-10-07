from flask import Flask, jsonify, request
from spotify_manager import SpotifyManager


app = Flask(__name__)
spotify_manager = SpotifyManager()

@app.route('/auth', methods=['POST'])
def auth():
    data = request.json
    access_token = data.get('access_token')
    if not access_token:
        return jsonify({"success": False, "message": "Access token is required"}), 400
    result = spotify_manager.start_with_access_token(access_token)
    return jsonify({"success": result})

@app.route('/status')
def status():
    return jsonify({"status": spotify_manager.get_status()})

if __name__ == '__main__':
    spotify_manager.start_from_cache()
    app.run(host='0.0.0.0', port=1234)