"""
Fetch a random plant from Perenual API and store as current plant of the day.
"""
import json
import logging
import os
import random
import urllib.request
import urllib.error

from . import store

logger = logging.getLogger(__name__)

PERENUAL_BASE = "https://perenual.com/api/v2/species/details"


def _get_api_key(app):
    """API key from env PLANT_API_KEY or app config."""
    key = (app.config.get("PLANT_API_KEY") or os.environ.get("PLANT_API_KEY") or "").strip()
    return key


def fetch_plant_of_the_day(app):
    """
    Pick a random unused species ID (1–2999), fetch from Perenual API, store as current.
    No-op if PLANT_API_KEY not set or API fails.
    """
    api_key = _get_api_key(app)
    if not api_key:
        logger.debug("PLANT_API_KEY not set; skipping plant of the day fetch.")
        return

    used = store.get_used_ids(app)
    available = [i for i in range(store.MIN_SPECIES_ID, store.MAX_SPECIES_ID + 1) if i not in used]
    if not available:
        logger.info("Plant of the day: all species IDs used; resetting and retrying.")
        used = set()
        available = list(range(store.MIN_SPECIES_ID, store.MAX_SPECIES_ID + 1))

    species_id = random.choice(available)
    url = f"{PERENUAL_BASE}/{species_id}?key={api_key}"

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning("Plant of the day API HTTP error %s: %s", e.code, e.reason)
        return
    except urllib.error.URLError as e:
        logger.warning("Plant of the day API URL error: %s", e.reason)
        return
    except Exception as e:
        logger.warning("Plant of the day fetch failed: %s", e)
        return

    if not data or not isinstance(data, dict):
        return

    store.add_used_id(app, species_id)
    store.set_current_plant(app, data)
    logger.info("Plant of the day set to species_id=%s (%s)", species_id, data.get("common_name"))
