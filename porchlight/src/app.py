from flask import Flask, jsonify, request
from ceiling_light_manager import CeilingLightManager

app = Flask(__name__)
ceiling_light = CeilingLightManager()

@app.route('/on')
def on():
    if not ceiling_light.is_on():
        ceiling_light.turn_on()
        print("Light turned on")
        return jsonify({"success": True, "message": "Light turned on"})
    else:
        print("Light is already on")
        return jsonify({"success": True, "message": "Light is already on"})

@app.route('/off')
def off():
    if ceiling_light.is_on():
        ceiling_light.turn_off()
        print("Light turned off")
        return jsonify({"success": True, "message": "Light turned off"})
    else:
        print("Light is already off")
        return jsonify({"success": True, "message": "Light is already off"})

if __name__ == '__main__':
    with ceiling_light:
        app.run(host='0.0.0.0', port=1234)