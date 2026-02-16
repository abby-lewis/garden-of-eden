"""
Persistent store for schedule rules. Uses a JSON file so the Pi doesn't need a database.
Rule times (start_time, end_time, time) are stored as HH:MM in device local time (Central).
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
    return {"rules": []}


def load_rules():
    """Load all rules from disk. Returns dict with 'rules' list."""
    path = _rules_path()
    with _LOCK:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rules = data.get("rules", [])
                    return {"rules": list(rules)}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load rules from %s: %s", path, e)
    return _default_rules()


def save_rules(data):
    """Save rules dict to disk. data must have 'rules' list."""
    path = _rules_path()
    with _LOCK:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
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
    rules = get_all_rules()
    rule = dict(rule)
    if not rule.get("id"):
        rule["id"] = str(uuid.uuid4())
    rules.append(rule)
    save_rules({"rules": rules})
    return rule


def update_rule(rule_id, updates):
    """
    Update an existing rule by id. Only provided keys are updated.
    Returns the updated rule or None if not found.
    """
    rules = get_all_rules()
    for i, r in enumerate(rules):
        if r.get("id") == rule_id:
            rules[i] = {**r, **updates, "id": rule_id}
            save_rules({"rules": rules})
            return rules[i]
    return None


def delete_rule(rule_id):
    """Remove a rule by id. Returns True if removed, False if not found."""
    rules = get_all_rules()
    for i, r in enumerate(rules):
        if r.get("id") == rule_id:
            rules.pop(i)
            save_rules({"rules": rules})
            return True
    return False
