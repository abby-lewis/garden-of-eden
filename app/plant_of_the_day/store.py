"""
Persist current plant of the day and set of used species IDs.
Files in instance/: plant_of_the_day_current.json, plant_of_the_day_used_ids.json
"""
import json
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

CURRENT_FILENAME = "plant_of_the_day_current.json"
USED_IDS_FILENAME = "plant_of_the_day_used_ids.json"
LOCK = Lock()

MIN_SPECIES_ID = 1
MAX_SPECIES_ID = 2999


def _current_path(app):
    return Path(app.instance_path) / CURRENT_FILENAME


def _used_ids_path(app):
    return Path(app.instance_path) / USED_IDS_FILENAME


def _load_used_ids_unsafe(app):
    """Load used IDs from file (caller must hold LOCK)."""
    path = _used_ids_path(app)
    if not path.exists():
        return set()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        ids = set(data.get("ids") or [])
        if len(ids) >= MAX_SPECIES_ID - MIN_SPECIES_ID + 1:
            return set()
        return ids
    except Exception as e:
        logger.warning("Could not load used plant IDs %s: %s", path, e)
        return set()


def get_used_ids(app):
    """Return set of species IDs already used for plant of the day."""
    with LOCK:
        return _load_used_ids_unsafe(app)


def add_used_id(app, species_id):
    """Mark a species ID as used. If all IDs 1-2999 used, clear and start over."""
    path = _used_ids_path(app)
    with LOCK:
        ids = _load_used_ids_unsafe(app)
        ids.add(species_id)
        if len(ids) >= MAX_SPECIES_ID - MIN_SPECIES_ID + 1:
            ids = set()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump({"ids": list(ids)}, f)
        except Exception as e:
            logger.warning("Could not save used plant IDs %s: %s", path, e)


def get_current_plant(app):
    """Return current plant of the day dict, or None."""
    path = _current_path(app)
    with LOCK:
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not load current plant %s: %s", path, e)
            return None


def set_current_plant(app, plant_data):
    """Save current plant of the day (full API response or subset)."""
    path = _current_path(app)
    with LOCK:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(plant_data, f, indent=2)
        except Exception as e:
            logger.warning("Could not save current plant %s: %s", path, e)
