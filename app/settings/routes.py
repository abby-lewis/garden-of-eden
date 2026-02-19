"""
REST API for app settings: gauge ranges, alert thresholds, and alert toggles.
Single row (id=1) in app_settings table.
"""
from flask import Blueprint, request, jsonify

from app.models import db, AppSettings

settings_blueprint = Blueprint("settings", __name__)

DEFAULTS = {
    "water_level_min": 13.0,
    "water_level_max": 8.5,
    "water_alert_threshold": 12.0,
    "air_temp_min": 32.0,
    "air_temp_max": 100.0,
    "air_temp_high_alert_threshold": 80.0,
    "air_temp_low_alert_threshold": 65.0,
    "humidity_min": 0.0,
    "humidity_max": 100.0,
    "humidity_low_alert_threshold": 40.0,
    "humidity_high_alert_threshold": 90.0,
    "pcb_temp_min": 75.0,
    "pcb_temp_max": 130.0,
    "pcb_temp_alert_threshold": 110.0,
    "water_level_alerts_enabled": False,
    "humidity_alerts_enabled": False,
    "air_temp_alerts_enabled": False,
    "pcb_temp_alerts_enabled": False,
}


def _get_or_create():
    row = AppSettings.query.get(1)
    if row is None:
        row = AppSettings(id=1, **DEFAULTS)
        db.session.add(row)
        db.session.commit()
    return row


def _float(val, default: float):
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _bool(val, default: bool):
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


@settings_blueprint.route("", methods=["GET"])
def get_settings():
    """Return current app settings (creates row with defaults if missing)."""
    row = _get_or_create()
    return jsonify(row.to_dict())


@settings_blueprint.route("", methods=["PUT", "PATCH"])
def update_settings():
    """Update app settings. Body can contain any subset of keys."""
    row = _get_or_create()
    body = request.get_json() or {}
    # Numeric
    for key in (
        "water_level_min", "water_level_max", "water_alert_threshold",
        "air_temp_min", "air_temp_max", "air_temp_high_alert_threshold", "air_temp_low_alert_threshold",
        "humidity_min", "humidity_max", "humidity_low_alert_threshold", "humidity_high_alert_threshold",
        "pcb_temp_min", "pcb_temp_max", "pcb_temp_alert_threshold",
    ):
        if key in body:
            setattr(row, key, _float(body[key], getattr(row, key)))
    # Booleans
    for key in ("water_level_alerts_enabled", "humidity_alerts_enabled", "air_temp_alerts_enabled", "pcb_temp_alerts_enabled"):
        if key in body:
            setattr(row, key, _bool(body[key], getattr(row, key)))
    db.session.commit()
    return jsonify(row.to_dict())
