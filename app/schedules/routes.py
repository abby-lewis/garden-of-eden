"""
REST API for schedule rules: list, create, update, delete.
Also: pause light/pump rules for N minutes (server-side), and schedule manual pump off.
"""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

from .store import (
    get_all_rules,
    get_rule,
    add_rule,
    update_rule,
    delete_rule,
    get_light_rules_paused_until,
    get_pump_rules_paused_until,
    set_light_rules_paused_until,
    set_pump_rules_paused_until,
    set_manual_pump_off_at,
)

schedule_blueprint = Blueprint("schedule", __name__)


def _normalize_time(s):
    """Normalize 'H:MM' or 'HH:MM' to 'HH:MM'."""
    if not s or ":" not in s:
        return None
    parts = s.strip().split(":")
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return "%02d:%02d" % (h, m)
    except (ValueError, IndexError):
        pass
    return None


def _validate_light_rule(body):
    """Return (error_message, None) or (None, normalized_dict)."""
    start = _normalize_time(body.get("start_time") or "")
    if start is None:
        return "start_time is required (HH:MM)", None
    end = (body.get("end_time") or "").strip() or None
    if end is not None:
        end = _normalize_time(end)
        if end is None:
            return "end_time must be HH:MM (00:00-23:59)", None
    brightness = body.get("brightness_pct", 0)
    try:
        brightness = int(brightness)
        if not (0 <= brightness <= 100):
            return "brightness_pct must be 0-100", None
    except (TypeError, ValueError):
        return "brightness_pct must be 0-100", None
    return None, {
        "type": "light",
        "start_time": start,
        "end_time": end,
        "brightness_pct": brightness,
        "enabled": body.get("enabled", True),
        "paused": body.get("paused", False),
    }


def _validate_pump_rule(body):
    """Return (error_message, None) or (None, normalized_dict)."""
    time_str = _normalize_time(body.get("time") or "")
    if time_str is None:
        return "time is required (HH:MM)", None
    try:
        duration = int(body.get("duration_minutes", 5))
        if duration < 1 or duration > 120:
            return "duration_minutes must be 1-120", None
    except (TypeError, ValueError):
        return "duration_minutes must be 1-120", None
    return None, {
        "type": "pump",
        "time": time_str,
        "duration_minutes": duration,
        "enabled": body.get("enabled", True),
        "paused": body.get("paused", False),
    }


@schedule_blueprint.route("", methods=["GET"])
def list_rules():
    """Return all rules and server-side pause-until times (for overlay UI)."""
    return jsonify(
        rules=get_all_rules(),
        light_rules_paused_until=get_light_rules_paused_until(),
        pump_rules_paused_until=get_pump_rules_paused_until(),
    )


@schedule_blueprint.route("/<rule_id>", methods=["GET"])
def get_one_rule(rule_id):
    """Return a single rule by id."""
    rule = get_rule(rule_id)
    if rule is None:
        return jsonify(error="Rule not found"), 404
    return jsonify(rule)


@schedule_blueprint.route("", methods=["POST"])
def create_rule():
    """Create a new rule. Body: type (light|pump) plus type-specific fields."""
    body = request.get_json() or {}
    rule_type = (body.get("type") or "").strip().lower()
    if rule_type == "light":
        err, data = _validate_light_rule(body)
        if err:
            return jsonify(error=err), 400
        rule = add_rule(data)
        return jsonify(rule), 201
    if rule_type == "pump":
        err, data = _validate_pump_rule(body)
        if err:
            return jsonify(error=err), 400
        rule = add_rule(data)
        return jsonify(rule), 201
    return jsonify(error="type must be 'light' or 'pump'"), 400


@schedule_blueprint.route("/<rule_id>", methods=["PUT"])
def update_one_rule(rule_id):
    """Update an existing rule. Body: fields to update."""
    rule = get_rule(rule_id)
    if rule is None:
        return jsonify(error="Rule not found"), 404
    body = request.get_json() or {}
    # Preserve type and validate by type
    rule_type = (body.get("type") or rule.get("type") or "").strip().lower()
    if rule_type == "light":
        err, data = _validate_light_rule({**rule, **body})
        if err:
            return jsonify(error=err), 400
        updated = update_rule(rule_id, data)
        return jsonify(updated)
    if rule_type == "pump":
        err, data = _validate_pump_rule({**rule, **body})
        if err:
            return jsonify(error=err), 400
        updated = update_rule(rule_id, data)
        return jsonify(updated)
    return jsonify(error="type must be 'light' or 'pump'"), 400


@schedule_blueprint.route("/<rule_id>", methods=["DELETE"])
def delete_one_rule(rule_id):
    """Delete a rule."""
    if delete_rule(rule_id):
        return "", 204
    return jsonify(error="Rule not found"), 404


def _parse_minutes(body, key="minutes", default=60, min_val=1, max_val=1440):
    """Parse minutes from JSON body. Returns (error_response, minutes or None)."""
    try:
        n = int(body.get(key, default))
        if min_val <= n <= max_val:
            return None, n
    except (TypeError, ValueError):
        pass
    return jsonify(error=f"{key} must be an integer between {min_val} and {max_val}"), None


@schedule_blueprint.route("/pause-light-rules", methods=["POST"])
def pause_light_rules():
    """Pause all light rules until now + body.minutes. Server holds the restore time."""
    body = request.get_json() or {}
    err, minutes = _parse_minutes(body, default=60, max_val=1440)
    if err:
        return err, 400
    until = datetime.now() + timedelta(minutes=minutes)
    set_light_rules_paused_until(until.isoformat())
    return "", 204


@schedule_blueprint.route("/pause-pump-rules", methods=["POST"])
def pause_pump_rules():
    """Pause all pump rules until now + body.minutes. Server holds the restore time."""
    body = request.get_json() or {}
    err, minutes = _parse_minutes(body, default=60, max_val=1440)
    if err:
        return err, 400
    until = datetime.now() + timedelta(minutes=minutes)
    set_pump_rules_paused_until(until.isoformat())
    return "", 204


@schedule_blueprint.route("/manual-pump-off", methods=["POST"])
def manual_pump_off():
    """Schedule pump to turn off in body.minutes. Scheduler will turn pump off at that time."""
    body = request.get_json() or {}
    err, minutes = _parse_minutes(body, default=5, max_val=120)
    if err:
        return err, 400
    off_at = datetime.now() + timedelta(minutes=minutes)
    set_manual_pump_off_at(off_at.isoformat())
    return "", 204


@schedule_blueprint.route("/resume-light-rules", methods=["POST"])
def resume_light_rules():
    """Clear light rules pause (resume rules immediately)."""
    set_light_rules_paused_until(None)
    return "", 204


@schedule_blueprint.route("/resume-pump-rules", methods=["POST"])
def resume_pump_rules():
    """Clear pump rules pause (resume rules immediately)."""
    set_pump_rules_paused_until(None)
    return "", 204
