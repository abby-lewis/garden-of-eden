"""
Send Plant of the Day to Slack at 9 AM: pun, name, image, and link.
Uses same Slack webhook/settings as other notifications.
"""
import json
import logging
import urllib.request
import urllib.error

from . import store
from .puns import pick_pun

logger = logging.getLogger(__name__)


def _more_info_url(plant):
    """Link to Perenual or species info if we have an id."""
    sid = plant.get("id")
    if sid is not None:
        return f"https://perenual.com/species-details/{sid}"
    return "https://perenual.com"


def send_plant_of_the_day_slack(app):
    """Send current plant of the day to Slack if enabled. No-op if no plant or Slack off."""
    with app.app_context():
        from app.settings.routes import _get_or_create
        row = _get_or_create()
        if not getattr(row, "slack_notifications_enabled", True):
            return
    plant = store.get_current_plant(app)
    if not plant:
        logger.debug("No plant of the day to send to Slack.")
        return
    url = _get_webhook_url(app)
    if not url:
        return
    common_name = (plant.get("common_name") or "Unknown plant").strip()
    image_url = None
    default_img = plant.get("default_image")
    if isinstance(default_img, dict):
        image_url = (default_img.get("regular_url") or default_img.get("medium_url") or default_img.get("thumbnail") or "").strip()
    more_url = _more_info_url(plant)
    pun = pick_pun()
    text = f"{pun}\n\n*Plant of the day: {common_name}*\n<{more_url}|View more on Perenual>"
    try:
        body = {"text": text}
        if image_url:
            body["attachments"] = [{"image_url": image_url}]
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        logger.warning("Plant of the day Slack send failed: %s", e)


def _get_webhook_url(app):
    with app.app_context():
        from app.settings.routes import _get_or_create
        row = _get_or_create()
        w = (row.slack_webhook_url or "").strip() if getattr(row, "slack_webhook_url", None) else None
        if w:
            return w
    import os
    return (os.environ.get("SLACK_WEBHOOK_URL") or "").strip() or None
