from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/on')
def on():
    return jsonify({"success": True, "message": "Not implemented"})

@app.route('/off')
def off():
    return jsonify({"success": True, "message": "Not implemented"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1234)