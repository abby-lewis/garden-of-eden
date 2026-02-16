#!/usr/bin/env python3
import logging

# Force I2C bus 1 for Raspberry Pi (Debian Trixie doesn't auto-detect)
import Adafruit_GPIO.I2C as I2C
_orig_get_default_bus = I2C.get_default_bus
def _patched_get_default_bus():
    try:
        return _orig_get_default_bus()
    except RuntimeError:
        return 1  # Pi typically uses /dev/i2c-1
I2C.get_default_bus = _patched_get_default_bus


from flask import jsonify, request
from app import create_app
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO,
                        format='%(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
# logging.basicConfig(filename='test.log', level=logging.DEBUG)

#logger = logging.getLogger(__name__)

app = create_app('default')
CORS(app)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
