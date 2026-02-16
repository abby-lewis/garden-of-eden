"""
Single shared AHT20/DHT20 sensor at 0x38 for both temperature and humidity.
One I2C read, cached values, and retries to avoid Errno 5.
"""
import time
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import config

import board
import adafruit_ahtx0

_sensor = None
_cached_temp = None
_cached_humidity = None
_cache_time = 0
_CACHE_SEC = 2.0
_RETRIES = 3
_RETRY_DELAY = 0.15

def get_sensor():
    global _sensor
    if _sensor is None:
        if config.SENSOR_TYPE != 'DHT20':
            raise ValueError("temp_humidity_shared only supports SENSOR_TYPE=DHT20 (AHT20 at 0x38)")
        i2c = board.I2C()
        _sensor = adafruit_ahtx0.AHTx0(i2c, address=0x38)
    return _sensor

def _read_both():
    """One I2C transaction; returns (temperature, relative_humidity). Retries on OSError 5."""
    s = get_sensor()
    last_err = None
    for attempt in range(_RETRIES):
        try:
            s._readdata()
            return (s.temperature, s.relative_humidity)
        except OSError as e:
            last_err = e
            if e.errno != 5:
                raise
            if attempt < _RETRIES - 1:
                time.sleep(_RETRY_DELAY)
    raise last_err

def read_temperature():
    global _cached_temp, _cached_humidity, _cache_time
    now = time.time()
    if _cached_temp is None or (now - _cache_time) > _CACHE_SEC:
        _cached_temp, _cached_humidity = _read_both()
        _cache_time = now
    return _cached_temp

def read_humidity():
    global _cached_temp, _cached_humidity, _cache_time
    now = time.time()
    if _cached_humidity is None or (now - _cache_time) > _CACHE_SEC:
        _cached_temp, _cached_humidity = _read_both()
        _cache_time = now
    return _cached_humidity
