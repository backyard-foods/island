import glob
import time
import threading
from datetime import datetime

class TempSensorManager:
    def __init__(self):
        self.base_dir = '/sys/bus/w1/devices/'
        self.sensors = {}
        self.update_connected_sensors()
        self.poll_interval = 30

    def update_connected_sensors(self):
        device_folders = glob.glob(self.base_dir + '28*')
        connected_sensors = set()
        for folder in device_folders:
            sensor_id = folder.split('/')[-1]
            connected_sensors.add(sensor_id)
            if sensor_id not in self.sensors:
                self.sensors[sensor_id] = {
                    'device_file': folder + '/w1_slave',
                    'last_reading': None,
                    'last_update': None
                }
        
        disconnected_sensors = set(self.sensors.keys()) - connected_sensors
        for sensor_id in disconnected_sensors:
            print(f"Disconnected sensor: {sensor_id}")
            del self.sensors[sensor_id]

        if len(self.sensors) > 0:
            self.poll_interval = 30
        else:
            self.poll_interval = 600

    def read_temp_raw(self, device_file):
        with open(device_file, 'r') as f:
            return f.readlines()

    def read_temp(self, sensor_id):
        device_file = self.sensors[sensor_id]['device_file']
        lines = self.read_temp_raw(device_file)
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = self.read_temp_raw(device_file)
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            self.sensors[sensor_id]['last_reading'] = temp_c
            self.sensors[sensor_id]['last_update'] = datetime.now().isoformat()
            return temp_c

    def get_sensor_count(self):
        return len(self.sensors)

    def get_last_readings(self):
        return {sensor_id: {
            'reading': data['last_reading'],
            'timestamp': data['last_update']
        } for sensor_id, data in self.sensors.items()}
    
    def get_events(self):
        connected_sensors = self.get_sensor_count()
        last_readings = self.get_last_readings()
        
        if not last_readings:
            return {"events": []}
        
        # Use the timestamp of the first sensor as the event timestamp
        timestamp = next(iter(last_readings.values()))['timestamp']
        
        values_c = {sensor_id: data['reading'] for sensor_id, data in last_readings.items()}
        
        event = {
            "type": "temperature",
            "timestamp": timestamp,
            "data": {
                "connectedSensors": connected_sensors,
                "valuesC": values_c
            }
        }
        
        return {"events": [event]}

    def update_all_sensors(self):
        self.update_connected_sensors()
        for sensor_id in self.sensors:
            self.read_temp(sensor_id)

    def check_temperatures(self):
        while True:
            self.update_all_sensors()
            print(f"Connected sensors: {self.get_sensor_count()}")
            print(f"Last readings: {self.get_last_readings()}")
            time.sleep(self.poll_interval)

    def start_temperature_checking(self):
        threading.Thread(target=self.check_temperatures, daemon=True).start()