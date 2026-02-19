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

# CORS: allow dashboard origins (local + prod) so browser allows requests from both.
# Explicit origins ensure Access-Control-Allow-Origin is set on every response (including 401 and OPTIONS).
try:
    import config as _config
    _origins = [_config.WEBAUTHN_ORIGIN_LOCAL]
    if getattr(_config, "WEBAUTHN_ORIGIN_PROD", "").strip():
        _origins.append(_config.WEBAUTHN_ORIGIN_PROD.strip())
except Exception:
    _origins = ["http://localhost:5173"]

CORS(
    app,
    origins=_origins,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    supports_credentials=False,
    expose_headers=None,
)

# Start rule-based scheduler (runs every minute)
try:
    from app.schedules.scheduler import start_scheduler
    start_scheduler()
except Exception as e:
    logging.warning("Schedule scheduler not started: %s", e)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
