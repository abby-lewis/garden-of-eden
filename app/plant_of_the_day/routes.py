"""GET /plant-of-the-day: return current plant for dashboard."""
import logging

from flask import Blueprint, jsonify, current_app

from . import store
from .slack_plant import _wikipedia_url

logger = logging.getLogger(__name__)
plant_of_the_day_blueprint = Blueprint("plant_of_the_day", __name__)


@plant_of_the_day_blueprint.route("", methods=["GET"])
def get_plant_of_the_day():
    """Return current plant of the day (full stored payload) or 404."""
    plant = store.get_current_plant(current_app)
    if plant is None:
        return jsonify({"error": "No plant of the day set"}), 404
    out = dict(plant)
    try:
        out["wikipedia_url"] = _wikipedia_url(plant)
    except Exception as e:
        logger.warning("Wikipedia URL failed for plant of the day: %s", e)
        out["wikipedia_url"] = None
    return jsonify(out)
