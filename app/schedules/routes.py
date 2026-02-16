"""
REST API for schedule rules: list, create, update, delete.
"""
from flask import Blueprint, request, jsonify

from .store import get_all_rules, get_rule, add_rule, update_rule, delete_rule

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
    }


@schedule_blueprint.route("", methods=["GET"])
def list_rules():
    """Return all rules."""
    return jsonify(rules=get_all_rules())


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
