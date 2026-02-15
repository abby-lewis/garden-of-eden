"""
Camera capture using fswebcam (USB cameras at /dev/video0, /dev/video1 or /dev/video2).
Uses config for device paths and resolution; supports capture to bytes or to disk.
Uses a per-device file lock so MQTT and Flask (or two requests) don't capture from the same camera at once.
"""
import fcntl
import logging
import os
import subprocess
import tempfile
import time
from typing import Optional, Tuple, List, Dict

try:
    from config import (
        UPPER_CAMERA_DEVICE,
        LOWER_CAMERA_DEVICE,
        CAMERA_RESOLUTION,
        UPPER_IMAGE_PATH,
        LOWER_IMAGE_PATH,
        UPPER_CAMERA_PALETTE,
        LOWER_CAMERA_PALETTE,
    )
except ImportError:
    UPPER_CAMERA_DEVICE = os.getenv("UPPER_CAMERA_DEVICE", "/dev/video0")
    LOWER_CAMERA_DEVICE = os.getenv("LOWER_CAMERA_DEVICE", "/dev/video2")
    CAMERA_RESOLUTION = os.getenv("CAMERA_RESOLUTION", "640x480")
    UPPER_IMAGE_PATH = os.getenv("UPPER_IMAGE_PATH", "/tmp/upper_camera.jpg")
    LOWER_IMAGE_PATH = os.getenv("LOWER_IMAGE_PATH", "/tmp/lower_camera.jpg")
    UPPER_CAMERA_PALETTE = os.getenv("UPPER_CAMERA_PALETTE", "").strip() or None
    LOWER_CAMERA_PALETTE = os.getenv("LOWER_CAMERA_PALETTE", "").strip() or None

logger = logging.getLogger(__name__)

# Device index to (device path, default temp path, optional palette) for capture
DEVICE_MAP = {
    0: (UPPER_CAMERA_DEVICE, UPPER_IMAGE_PATH, UPPER_CAMERA_PALETTE),
    1: (LOWER_CAMERA_DEVICE, LOWER_IMAGE_PATH, LOWER_CAMERA_PALETTE),
}


class CameraError(Exception):
    """Raised when capture or device access fails."""
    pass


def _device_lock_path(device_id: int) -> str:
    """Path to a lock file so only one process captures from this device at a time."""
    return f"/tmp/gardyn_camera_{device_id}.lock"


def _capture_lock(device_id: int):
    """Context manager: hold an exclusive lock on this camera device (cross-process)."""
    path = _device_lock_path(device_id)
    fd = os.open(path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class Camera:
    """Control for USB cameras via fswebcam."""

    def __init__(
        self,
        resolution: Optional[str] = None,
        skip_frames: int = 2,
        frame_interval: int = 2,
    ):
        self.resolution = resolution or CAMERA_RESOLUTION
        self.skip_frames = skip_frames
        self.frame_interval = frame_interval
        self._stream_cap = None  # Optional OpenCV VideoCapture for streaming

    def list_devices(self) -> List[Dict]:
        """Return list of configured camera devices (id, device path, name)."""
        return [
            {"id": 0, "device": UPPER_CAMERA_DEVICE, "name": "upper"},
            {"id": 1, "device": LOWER_CAMERA_DEVICE, "name": "lower"},
        ]

    def _device_for_id(self, device_id: int) -> Tuple[str, str, Optional[str]]:
        device_id = int(device_id)
        if device_id not in DEVICE_MAP:
            raise ValueError(f"device must be 0 or 1, got {device_id}")
        return DEVICE_MAP[device_id]

    def capture(
        self,
        device_id: int = 0,
        save_dir: Optional[str] = None,
    ) -> Tuple[bytes, Optional[str]]:
        """
        Capture a single frame from the given camera.

        Args:
            device_id: 0 = upper camera, 1 = lower camera.
            save_dir: If set, save image here with a timestamped filename and return path.

        Returns:
            (jpeg_bytes, saved_path_or_none)

        Raises:
            CameraError: If fswebcam fails or device is unavailable.
        """
        device_path, default_path, palette = self._device_for_id(device_id)
        out_path = default_path
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            out_path = os.path.join(
                save_dir,
                f"camera_{device_id}_{int(time.time())}.jpg"
            )
        cmd = [
            "fswebcam",
            "-d", device_path,
            "-r", self.resolution,
            "-S", str(self.skip_frames),
            "-F", str(self.frame_interval),
            "--no-banner",
            out_path,
        ]
        if palette:
            cmd.extend(["-p", palette])
        try:
            with _capture_lock(device_id):
                subprocess.check_call(cmd, timeout=30)
                if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
                    raise CameraError(
                        "Capture produced no output file; device may not support the requested format. "
                        "Try setting UPPER_CAMERA_PALETTE=MJPEG or LOWER_CAMERA_PALETTE=MJPEG in .env for that camera."
                    )
                with open(out_path, "rb") as f:
                    data = f.read()
        except subprocess.CalledProcessError as e:
            logger.exception("fswebcam capture failed: %s", e)
            raise CameraError(f"Capture failed: {e}") from e
        except FileNotFoundError:
            raise CameraError("fswebcam not installed (apt install fswebcam)") from None
        except subprocess.TimeoutExpired:
            raise CameraError("Capture timed out") from None

        return data, out_path if save_dir else None

    def capture_to_bytes(self, device_id: int = 0) -> bytes:
        """Capture and return JPEG bytes only (no save)."""
        data, _ = self.capture(device_id=device_id, save_dir=None)
        return data

    def stream_frames(self, device_id: int = 0):
        """
        Generator that yields MJPEG frames for live streaming.
        Requires opencv-python-headless; yields (bytes, None) chunks for multipart response.
        """
        try:
            import cv2
        except ImportError:
            raise CameraError(
                "Live stream requires opencv-python-headless: pip install opencv-python-headless"
            ) from None
        device_path, _, _ = self._device_for_id(device_id)
        cap = cv2.VideoCapture(device_path)
        if not cap.isOpened():
            raise CameraError(f"Cannot open camera at {device_path}")
        try:
            # Prefer a small resolution for Pi Zero
            w, h = (640, 480) if "x" in self.resolution else (640, 480)
            if "x" in self.resolution:
                parts = self.resolution.lower().split("x")
                if len(parts) == 2:
                    w, h = int(parts[0]), int(parts[1])
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                _, buf = cv2.imencode(".jpg", frame)
                yield buf.tobytes()
        finally:
            cap.release()

    def close(self):
        """Release any streaming resources."""
        if self._stream_cap is not None:
            try:
                self._stream_cap.release()
            except Exception:
                pass
            self._stream_cap = None
