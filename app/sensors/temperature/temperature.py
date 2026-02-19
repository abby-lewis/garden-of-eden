"""Temperature from shared DHT20/AHT20 sensor at 0x38."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.sensors.temp_humidity_shared import read_temperature

class TemperatureSensor:
    def read(self):
        return read_temperature()

temperature_sensor = None
try:
    from app.sensors.temp_humidity_shared import get_sensor
    get_sensor()  # init once
    temperature_sensor = TemperatureSensor()
except Exception as e:
    print("Failed to initiate temperature sensor:", e)
