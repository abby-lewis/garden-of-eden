#!/usr/bin/env python3
"""
Update the stored plant-of-the-day entry by re-fetching a given Perenual species ID
and overwriting the current plant JSON. Use when stored data was wrong and the
Wikipedia URL (or other fields) need to be fixed.

Usage (from garden-of-eden repo root, with venv activated):
  python -m scripts.update_plant_entry 2388

Requires PLANT_API_KEY in .env or environment.
"""
import json
import os
import sys
import urllib.request
import urllib.error

# Repo root and load .env before importing app
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)
_env_path = os.path.join(_repo_root, ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"").strip()
                if k:
                    os.environ.setdefault(k, v)
try:
    from dotenv import load_dotenv
    load_dotenv(_repo_root)
except ImportError:
    pass

from app import create_app
from app.plant_of_the_day import store

PERENUAL_BASE = "https://perenual.com/api/v2/species/details"


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.update_plant_entry <perenual_species_id>", file=sys.stderr)
        print("Example: python -m scripts.update_plant_entry 2388", file=sys.stderr)
        sys.exit(1)
    species_id = sys.argv[1].strip()
    api_key = (os.environ.get("PLANT_API_KEY") or "").strip()
    if not api_key:
        print("PLANT_API_KEY not set. Add it to .env or the environment.", file=sys.stderr)
        sys.exit(1)

    url = f"{PERENUAL_BASE}/{species_id}?key={api_key}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Perenual API error: {e.code} {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not data or not isinstance(data, dict):
        print("Invalid API response.", file=sys.stderr)
        sys.exit(1)

    app = create_app("default")
    with app.app_context():
        store.set_current_plant(app, data)

    common = (data.get("common_name") or "").strip()
    genus = (data.get("genus") or "").strip()
    epithet = (data.get("species_epithet") or "").strip()
    print(f"Updated plant-of-the-day to species ID {species_id}: {common!r}")
    print(f"  genus={genus!r}, species_epithet={epithet!r}")
    print("  Stored at: instance/plant_of_the_day_current.json")


if __name__ == "__main__":
    main()
