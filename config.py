import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Auth and database (passkey auth)
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")
# SQLite DB under instance/ so it's next to the app
_instance = Path(__file__).resolve().parent / "instance"
_instance.mkdir(exist_ok=True)
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", f"sqlite:///{_instance}/garden.db")
# WebAuthn: must match the origin of the dashboard (e.g. https://your-host:8444 or http://localhost:5173)
WEBAUTHN_RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
WEBAUTHN_ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:5173")
WEBAUTHN_RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "Garden of Eden")
# JWT
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
# Comma-separated list of email addresses allowed to register and sign in
ALLOWED_EMAILS = [e.strip().lower() for e in os.getenv("ALLOWED_EMAILS", "").strip().split(",") if e.strip()]

# MQTT configurations
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
KEEP_ALIVE_INTERVAL = int(os.getenv("MQTT_KEEPALIVE_INTERVAL", "60"))

# Topic configurations
VERSION = os.getenv("MQTT_VERSION", "1.0.0")
IDENTIFIER = os.getenv("MQTT_IDENTIFIER", "gardyn-xx")
MODEL= os.getenv("MQTT_DEVICE_MODEL", "gardyn 3.0")
BASE_TOPIC = os.getenv("MQTT_BASETOPIC", "gardyn")

USERNAME = os.getenv("MQTT_USERNAME")
PASSWORD = os.getenv("MQTT_PASSWORD")

SENSOR_TYPE = os.getenv('SENSOR_TYPE')

WATER_LOW_CM = float(os.getenv("WATER_LOW_CM", 0)) or None

UPPER_CAMERA_DEVICE = os.getenv("UPPER_CAMERA_DEVICE", "/dev/video0")
LOWER_CAMERA_DEVICE = os.getenv("LOWER_CAMERA_DEVICE", "/dev/video2")
UPPER_IMAGE_PATH = os.getenv("UPPER_IMAGE_PATH", "/tmp/upper_camera.jpg")
LOWER_IMAGE_PATH = os.getenv("LOWER_IMAGE_PATH", "/tmp/lower_camera.jpg")
CAMERA_RESOLUTION = os.getenv("CAMERA_RESOLUTION", "640x480")
# Optional: force palette for cameras that report "Unable to find a compatible palette format" (e.g. MJPEG, YUYV)
UPPER_CAMERA_PALETTE = os.getenv("UPPER_CAMERA_PALETTE", "").strip() or None
LOWER_CAMERA_PALETTE = os.getenv("LOWER_CAMERA_PALETTE", "").strip() or None
IMAGE_INTERVAL_SECONDS = int(os.getenv("IMAGE_INTERVAL_SECONDS", "3600"))
# Where to save "Capture & save" photos. Relative paths are relative to GARDYN_PROJECT_ROOT.
CAMERA_PHOTOS_DIR = os.getenv("CAMERA_PHOTOS_DIR", "photos")
GARDYN_PROJECT_ROOT = os.getenv("GARDYN_PROJECT_ROOT", os.getcwd())
CAMERA_PHOTOS_DIR_RESOLVED = (
    os.path.join(GARDYN_PROJECT_ROOT, CAMERA_PHOTOS_DIR)
    if not os.path.isabs(CAMERA_PHOTOS_DIR)
    else CAMERA_PHOTOS_DIR
)
