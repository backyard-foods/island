import RPi.GPIO as GPIO
import os

LOG_PREFIX = "[ceiling-light]"

LIGHT_PIN = int(os.environ['CEILING_LIGHT_GPIO_PIN'])

class CeilingLightManager:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LIGHT_PIN, GPIO.OUT, initial=GPIO.LOW)
        
    def is_on(self):
        try:
            return GPIO.input(LIGHT_PIN) == GPIO.HIGH
        except Exception as e:
            print(f"{LOG_PREFIX} Error getting status: {e}")
            return False

    def turn_on(self):
        GPIO.output(LIGHT_PIN, GPIO.HIGH)

    def turn_off(self):
        GPIO.output(LIGHT_PIN, GPIO.LOW)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()

    def cleanup(self):
        GPIO.cleanup(LIGHT_PIN)
        print(f"{LOG_PREFIX} GPIO cleanup completed for pin {LIGHT_PIN}")
    
