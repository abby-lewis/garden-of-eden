"""Humidity from shared DHT20/AHT20 sensor at 0x38."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.sensors.temp_humidity_shared import read_humidity

class HumiditySensor:
    def read(self):
        return read_humidity()

humidity_sensor = None
try:
    from app.sensors.temp_humidity_shared import get_sensor
    get_sensor()
    humidity_sensor = HumiditySensor()
except Exception as e:
    print("Failed to initiate humidity sensor:", e)
