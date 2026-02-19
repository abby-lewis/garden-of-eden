"""
Send Plant of the Day to Slack at 9 AM: pun, name, image, and link.
Uses same Slack webhook/settings as other notifications.
"""
import json
import logging
import urllib.parse
import urllib.request
import urllib.error

from . import store
from .puns import pick_pun

logger = logging.getLogger(__name__)

WIKI_BASE = "https://en.wikipedia.org/wiki/"


def _wikipedia_url(plant):
    """Build Wikipedia article URL from genus + species epithet, or fallback to scientific_name/common_name."""
    genus = (plant.get("genus") or "").strip()
    epithet = (plant.get("species_epithet") or "").strip()
    if genus and epithet:
        title = f"{genus} {epithet}"
    else:
        sci = plant.get("scientific_name")
        if isinstance(sci, list) and sci and isinstance(sci[0], str) and sci[0].strip():
            title = sci[0].strip()
        else:
            title = (plant.get("common_name") or "Plant").strip()
    if not title:
        return WIKI_BASE + "Plant"
    title = title.replace(" ", "_")
    return WIKI_BASE + urllib.parse.quote(title, safe="/_")


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
    more_url = _wikipedia_url(plant)
    pun = pick_pun()
    text = f"{pun}\n\n*Plant of the day: {common_name}*\n<{more_url}|View on Wikipedia>"
    try:
        body = {"text": text}
        if image_url:
            # Block Kit image block so Slack displays the photo
            body["blocks"] = [
                {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                {"type": "image", "image_url": image_url, "alt_text": common_name},
            ]
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
