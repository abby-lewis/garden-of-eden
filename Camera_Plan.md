# Pi camera add-on for garden-of-eden

This add-on exposes HTTP endpoints that run `bin/take-pictures.sh` and serve the resulting images so the Gardyn dashboard can display them.

---

## Plan of attack (cameras)

**Goal:** Show live(ish) upper and lower camera images in the Gardyn React dashboard.

**Why the Pi addon is needed:** garden-of-eden doesn’t expose camera routes. The repo has `bin/take-pictures.sh`, which uses `fswebcam` to capture from `/dev/video0` and `/dev/video2` into `/tmp/upper_cam.jpg` and `/tmp/lower_cam.jpg`, but nothing in Flask serves those over HTTP. The dashboard can’t display images without a URL that returns JPEGs.

**Strategy:**

1. **Reuse the existing script** – Don’t change `take-pictures.sh`. It already does the right thing (two cameras, known paths). We just need the Pi to run it and serve the files over HTTP.

2. **Add a small Flask “camera” blueprint on the Pi** – New routes that:
   - On each request, run `bin/take-pictures.sh` (so the image is fresh).
   - Then serve the corresponding file as JPEG: `GET /camera/upper` → `/tmp/upper_cam.jpg`, `GET /camera/lower` → `/tmp/lower_cam.jpg`.

3. **Dashboard** – The React app already has a Camera section that:
   - Calls `GET /camera/upper` and `GET /camera/lower` (with cache-busting).
   - Shows “Upper” and “Lower” images and a “Take picture” button to refresh both.
   - If those endpoints don’t exist yet, it shows an error and points you to this README.

4. **Permissions** – The script uses `sudo fswebcam`. So on the Pi you either run Flask with `sudo` or add a sudoers entry so the script can run without a password. No change to the script itself.

**Flow:** User clicks “Take picture” in the dashboard → browser requests `/camera/upper` and `/camera/lower` → Flask runs `take-pictures.sh` (updates both files) and sends the JPEGs → dashboard displays them.

**Summary:** Add this addon (copy camera blueprint, register it, fix permissions), restart the Flask app, and the dashboard camera section will work without any further code changes.

---

## 1. Copy files to your Pi

On the Pi, in your garden-of-eden repo:

- Copy the `app/sensors/camera` folder into `app/sensors/` so you have:
  - `app/sensors/camera/__init__.py`
  - `app/sensors/camera/routes.py`

## 2. Register the blueprint

In `app/__init__.py`, add:

```python
from .sensors.camera.routes import camera_blueprint
# ...
app.register_blueprint(camera_blueprint, url_prefix='/camera')
```

So the top of `app/__init__.py` looks like:

```python
from flask import Flask
from .sensors.light.routes import light_blueprint
from .sensors.pump.routes import pump_blueprint
from .sensors.distance.routes import distance_blueprint
from .sensors.temperature.routes import temperature_blueprint
from .sensors.humidity.routes import humidity_blueprint
from .sensors.pcb_temp.routes import pcb_temp_blueprint
from .sensors.camera.routes import camera_blueprint

def create_app(config_name):
    app = Flask(__name__)
    # ...
    app.register_blueprint(light_blueprint, url_prefix='/light')
    app.register_blueprint(pump_blueprint, url_prefix='/pump')
    app.register_blueprint(distance_blueprint, url_prefix='/distance')
    app.register_blueprint(temperature_blueprint, url_prefix='/temperature')
    app.register_blueprint(humidity_blueprint, url_prefix='/humidity')
    app.register_blueprint(pcb_temp_blueprint, url_prefix='/pcb-temp')
    app.register_blueprint(camera_blueprint, url_prefix='/camera')
    return app
```

## 3. Script and permissions

- Ensure `bin/take-pictures.sh` is executable: `chmod +x bin/take-pictures.sh`.
- The script uses `sudo fswebcam`. So either:
  - Run the Flask app as root (e.g. `sudo python run.py`), or
  - Allow passwordless sudo for the script for the user that runs Flask, e.g.:
    - Run `sudo visudo` and add:
    - `gardyn ALL=(ALL) NOPASSWD: /home/gardyn/garden-of-eden/bin/take-pictures.sh`
    - (Replace path and username as needed.)

Optional env vars (set before starting the app):

- `GARDYN_PROJECT_ROOT` – project root (default: current working directory when the app starts). Set if you start the app from a different directory.
- `GARDYN_CAMERA_SUDO=0` – set to disable `sudo` when calling the script (use if the app runs as root or has permission to access `/dev/video*` without sudo).

## 4. Endpoints

After restarting the Flask app:

- `GET /camera/upper` – runs `take-pictures.sh`, then returns `/tmp/upper_cam.jpg`.
- `GET /camera/lower` – runs `take-pictures.sh`, then returns `/tmp/lower_cam.jpg`.

The dashboard will show both and a “Refresh” to fetch new images.
