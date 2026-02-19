"""
Persistent state for threshold alerts: in_alarm and last_sent times per key.
Used to send only on transition to alarm (or recovery) and to enforce cooldown.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

FILENAME = "alert_state.json"

# Alert keys (must match keys used in slack_alerts)
ALERT_KEYS = (
    "water_low",
    "air_temp_high",
    "air_temp_low",
    "humidity_low",
    "humidity_high",
    "pcb_temp_high",
)

_lock = Lock()


def _state_path(app):
    return Path(app.instance_path) / FILENAME


def _load(app):
    path = _state_path(app)
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load alert state %s: %s", path, e)
        return {}


def _save(app, data):
    path = _state_path(app)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("Could not save alert state %s: %s", path, e)


def get_state(app, key):
    """Return dict with in_alarm (bool), last_sent_at (ISO str or None), last_recovery_at (ISO str or None)."""
    with _lock:
        data = _load(app)
    entry = data.get(key) or {}
    return {
        "in_alarm": bool(entry.get("in_alarm")),
        "last_sent_at": entry.get("last_sent_at"),
        "last_recovery_at": entry.get("last_recovery_at"),
    }


def set_alarm_sent(app, key):
    """Mark key as in alarm and set last_sent_at to now."""
    with _lock:
        data = _load(app)
        data.setdefault(key, {})["in_alarm"] = True
        data[key]["last_sent_at"] = datetime.utcnow().isoformat() + "Z"
        _save(app, data)


def set_recovery_sent(app, key):
    """Mark key as not in alarm and set last_recovery_at to now."""
    with _lock:
        data = _load(app)
        data.setdefault(key, {})["in_alarm"] = False
        data[key]["last_recovery_at"] = datetime.utcnow().isoformat() + "Z"
        _save(app, data)


def set_in_alarm(app, key, in_alarm):
    """Update in_alarm flag without changing last_sent_at (e.g. when in alarm but cooldown prevented send)."""
    with _lock:
        data = _load(app)
        data.setdefault(key, {})["in_alarm"] = bool(in_alarm)
        _save(app, data)


def can_send_alert(app, key, cooldown_minutes):
    """True if we have not sent an alert for this key within cooldown_minutes."""
    state = get_state(app, key)
    if not state["last_sent_at"]:
        return True
    try:
        last = datetime.fromisoformat(state["last_sent_at"].replace("Z", "+00:00"))
        from datetime import timezone
        if last.tzinfo:
            last = last.replace(tzinfo=None)  # naive compare with utcnow
        else:
            last = last
        delta_min = (datetime.utcnow() - last).total_seconds() / 60
        return delta_min >= cooldown_minutes
    except Exception:
        return True


def can_send_recovery(app, key, cooldown_minutes):
    """True if we have not sent a recovery for this key within cooldown_minutes."""
    state = get_state(app, key)
    if not state.get("last_recovery_at"):
        return True
    try:
        last = datetime.fromisoformat(state["last_recovery_at"].replace("Z", "+00:00"))
        if last.tzinfo:
            last = last.replace(tzinfo=None)
        delta_min = (datetime.utcnow() - last).total_seconds() / 60
        return delta_min >= cooldown_minutes
    except Exception:
        return True
