"""
Persistent store for schedule rules. Uses a JSON file so the Pi doesn't need a database.
Rule times (start_time, end_time, time) are stored as HH:MM in device local time (Central).

Also stores server-side overrides:
- light_rules_paused_until: ISO datetime; scheduler skips light rules until this time.
- pump_rules_paused_until: ISO datetime; scheduler skips pump rules until this time.
- manual_pump_off_at: ISO datetime; scheduler turns pump off at this time (for manual watering).
"""
import json
import logging
import os
import threading
import uuid

logger = logging.getLogger(__name__)

# Default path: project root or env
def _rules_path():
    root = os.environ.get("GARDYN_PROJECT_ROOT", os.getcwd())
    return os.path.join(root, "schedule_rules.json")


_LOCK = threading.Lock()


def _default_rules():
    return {
        "rules": [],
        "light_rules_paused_until": None,
        "pump_rules_paused_until": None,
        "manual_pump_off_at": None,
    }


def load_rules():
    """Load all rules and overrides from disk. Returns dict with 'rules' list and override keys."""
    path = _rules_path()
    with _LOCK:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rules = data.get("rules", [])
                    return {
                        "rules": list(rules),
                        "light_rules_paused_until": data.get("light_rules_paused_until"),
                        "pump_rules_paused_until": data.get("pump_rules_paused_until"),
                        "manual_pump_off_at": data.get("manual_pump_off_at"),
                    }
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load rules from %s: %s", path, e)
    return _default_rules()


def save_rules(data):
    """Save full state to disk. data should include 'rules' and override keys (callers pass load_rules() then modify)."""
    path = _rules_path()
    out = {
        "rules": data.get("rules", []),
        "light_rules_paused_until": data.get("light_rules_paused_until"),
        "pump_rules_paused_until": data.get("pump_rules_paused_until"),
        "manual_pump_off_at": data.get("manual_pump_off_at"),
    }
    with _LOCK:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except OSError as e:
            logger.error("Could not save rules to %s: %s", path, e)
            raise


def get_all_rules():
    """Return list of all rules."""
    return load_rules()["rules"]


def get_rule(rule_id):
    """Return a single rule by id or None."""
    for r in get_all_rules():
        if r.get("id") == rule_id:
            return r
    return None


def add_rule(rule):
    """
    Add a new rule. 'id' will be generated if missing.
    Returns the rule as stored (with id).
    """
    data = load_rules()
    rule = dict(rule)
    if not rule.get("id"):
        rule["id"] = str(uuid.uuid4())
    data["rules"] = data["rules"] + [rule]
    save_rules(data)
    return rule


def update_rule(rule_id, updates):
    """
    Update an existing rule by id. Only provided keys are updated.
    Returns the updated rule or None if not found.
    """
    data = load_rules()
    for i, r in enumerate(data["rules"]):
        if r.get("id") == rule_id:
            data["rules"][i] = {**r, **updates, "id": rule_id}
            save_rules(data)
            return data["rules"][i]
    return None


def delete_rule(rule_id):
    """Remove a rule by id. Returns True if removed, False if not found."""
    data = load_rules()
    for i, r in enumerate(data["rules"]):
        if r.get("id") == rule_id:
            data["rules"].pop(i)
            save_rules(data)
            return True
    return False


def _get_overrides():
    """Return current overrides dict (without rules)."""
    data = load_rules()
    return {
        "light_rules_paused_until": data.get("light_rules_paused_until"),
        "pump_rules_paused_until": data.get("pump_rules_paused_until"),
        "manual_pump_off_at": data.get("manual_pump_off_at"),
    }


def get_light_rules_paused_until():
    """Return ISO datetime string or None. Scheduler skips light rules until this time."""
    return load_rules().get("light_rules_paused_until")


def set_light_rules_paused_until(iso_datetime):
    """Set light rules paused until the given ISO datetime (or None to clear)."""
    data = load_rules()
    data["light_rules_paused_until"] = iso_datetime
    save_rules(data)


def get_pump_rules_paused_until():
    """Return ISO datetime string or None. Scheduler skips pump rules until this time."""
    return load_rules().get("pump_rules_paused_until")


def set_pump_rules_paused_until(iso_datetime):
    """Set pump rules paused until the given ISO datetime (or None to clear)."""
    data = load_rules()
    data["pump_rules_paused_until"] = iso_datetime
    save_rules(data)


def get_manual_pump_off_at():
    """Return ISO datetime string or None. Scheduler turns pump off at this time."""
    return load_rules().get("manual_pump_off_at")


def set_manual_pump_off_at(iso_datetime):
    """Set manual pump off time (or None to clear)."""
    data = load_rules()
    data["manual_pump_off_at"] = iso_datetime
    save_rules(data)
