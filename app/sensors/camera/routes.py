"""
Camera REST API (snapshots only; no live stream):
- GET /upper, GET /lower: take a picture and return JPEG (client can poll for live-ish view).
- POST /capture: take a picture (return image or save to disk).
- Photos: list and serve saved photos.
"""
import os
from flask import Blueprint, request, jsonify, Response, send_from_directory
from app.lib.lib import check_sensor_guard
from .camera import Camera, CameraError

try:
    from config import CAMERA_PHOTOS_DIR_RESOLVED
except ImportError:
    CAMERA_PHOTOS_DIR_RESOLVED = os.path.join(os.getcwd(), "photos")

camera_blueprint = Blueprint("camera", __name__)
camera_control = Camera()
check_sensor = check_sensor_guard(sensor=camera_control, sensor_name="Camera")


def _device_id_from_request() -> int:
    """Parse device from query or JSON body; default 0."""
    device = request.args.get("device")
    if device is None and request.is_json:
        device = request.get_json(silent=True) or {}
        device = device.get("device", 0)
    if device in ("upper", "0"):
        return 0
    if device in ("lower", "1"):
        return 1
    try:
        return int(device) if device is not None else 0
    except (TypeError, ValueError):
        return 0


@camera_blueprint.route("/upper", methods=["GET"])
@check_sensor
def snapshot_upper():
    """Snapshot from upper camera (JPEG). Backward compatible."""
    try:
        jpeg_bytes, _ = camera_control.capture(device_id=0, save_dir=None)
        return Response(jpeg_bytes, mimetype="image/jpeg")
    except CameraError as e:
        return jsonify(error=str(e)), 503


@camera_blueprint.route("/lower", methods=["GET"])
@check_sensor
def snapshot_lower():
    """Snapshot from lower camera (JPEG). Backward compatible."""
    try:
        jpeg_bytes, _ = camera_control.capture(device_id=1, save_dir=None)
        return Response(jpeg_bytes, mimetype="image/jpeg")
    except CameraError as e:
        return jsonify(error=str(e)), 503


@camera_blueprint.route("/devices", methods=["GET"])
@check_sensor
def list_devices():
    """List configured cameras (id, device path, name)."""
    return jsonify(devices=camera_control.list_devices()), 200


@camera_blueprint.route("/capture", methods=["POST"])
@check_sensor
def capture():
    """
    Take a picture from the specified camera.

    Query/body: device=0|1|upper|lower (default 0), save=0|1 (default 0).

    - save=0: Return the image immediately as image/jpeg (no storage).
    - save=1: Save to project_root/photos (or CAMERA_PHOTOS_DIR) and return JSON with url and path.
    """
    device_id = _device_id_from_request()
    save = request.args.get("save", "0").strip().lower() in ("1", "true", "yes")
    if not save and request.is_json:
        body = request.get_json(silent=True) or {}
        save = body.get("save", False) in (True, 1, "1", "true", "yes")

    save_dir = CAMERA_PHOTOS_DIR_RESOLVED if save else None
    try:
        jpeg_bytes, saved_path = camera_control.capture(device_id=device_id, save_dir=save_dir)
    except CameraError as e:
        return jsonify(error=str(e)), 503
    except ValueError as e:
        return jsonify(error=str(e)), 400

    if save and saved_path:
        filename = os.path.basename(saved_path)
        return jsonify(
            message="Photo saved",
            path=saved_path,
            filename=filename,
            url=f"/camera/photos/{filename}",
        ), 200

    return Response(jpeg_bytes, mimetype="image/jpeg")


@camera_blueprint.route("/photos", methods=["GET"])
@check_sensor
def list_photos():
    """
    List saved photo filenames and URLs (from project_root/photos by default).
    """
    if not os.path.isdir(CAMERA_PHOTOS_DIR_RESOLVED):
        return jsonify(photos=[], message="Photo directory does not exist yet"), 200
    try:
        files = [
            f for f in os.listdir(CAMERA_PHOTOS_DIR_RESOLVED)
            if f.lower().endswith((".jpg", ".jpeg"))
        ]
        files.sort(reverse=True)
        photos = [{"filename": f, "url": f"/camera/photos/{f}"} for f in files]
        return jsonify(photos=photos), 200
    except OSError as e:
        return jsonify(error=str(e)), 503


def _validate_photo_filename(filename: str) -> bool:
    """Reject path traversal and path separators."""
    return bool(filename) and ".." not in filename and os.path.sep not in filename


@camera_blueprint.route("/photos/<path:filename>", methods=["GET"])
@check_sensor
def get_photo(filename):
    """Serve a saved photo by filename (from project_root/photos by default)."""
    if not os.path.isdir(CAMERA_PHOTOS_DIR_RESOLVED):
        return jsonify(error="Photo directory not available"), 404
    if not _validate_photo_filename(filename):
        return jsonify(error="Invalid filename"), 400
    try:
        return send_from_directory(CAMERA_PHOTOS_DIR_RESOLVED, filename, mimetype="image/jpeg")
    except OSError:
        return jsonify(error="Not found"), 404


@camera_blueprint.route("/photos/<path:filename>", methods=["DELETE"])
@check_sensor
def delete_photo(filename):
    """Delete a saved photo by filename."""
    if not os.path.isdir(CAMERA_PHOTOS_DIR_RESOLVED):
        return jsonify(error="Photo directory not available"), 404
    if not _validate_photo_filename(filename):
        return jsonify(error="Invalid filename"), 400
    path = os.path.join(CAMERA_PHOTOS_DIR_RESOLVED, filename)
    if not os.path.isfile(path):
        return jsonify(error="Not found"), 404
    try:
        os.remove(path)
        return "", 204
    except OSError as e:
        return jsonify(error=str(e)), 500
