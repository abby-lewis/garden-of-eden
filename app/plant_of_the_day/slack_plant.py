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
WIKI_API = "https://en.wikipedia.org/w/api.php"


def _wiki_title_to_url(title):
    """Convert a wiki title (e.g. 'Cornus florida') to the article URL."""
    if not title or not title.strip():
        return WIKI_BASE + "Plant"
    title = title.strip().replace(" ", "_")
    return WIKI_BASE + urllib.parse.quote(title, safe="/_")


def _wikipedia_page_exists(title):
    """Return True if a Wikipedia article exists for the given title (e.g. 'Cornus florida')."""
    if not title or not title.strip():
        return False
    title = title.strip().replace(" ", "_")
    url = f"{WIKI_API}?action=query&titles={urllib.parse.quote(title, safe='')}&format=json"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        pages = (data.get("query") or {}).get("pages") or {}
        for page_id, page in pages.items():
            if str(page_id) != "-1" and "missing" not in page:
                return True
        return False
    except Exception as e:
        logger.debug("Wikipedia API check failed for %r: %s", title, e)
        return False


def _wikipedia_url(plant):
    """Build Wikipedia article URL from Perenual API genus + species_epithet (e.g. Cornus florida).
    Uses only genus and species_epithet when both are present. Check genus+epithet first;
    if that page exists, use it. If not, fall back to genus-only when that page exists.
    """
    genus = (plant.get("genus") or "").strip()
    epithet = (plant.get("species_epithet") or "").strip()

    if genus and epithet:
        species_title = f"{genus} {epithet}"
        if _wikipedia_page_exists(species_title):
            return _wiki_title_to_url(species_title)
        if _wikipedia_page_exists(genus):
            return _wiki_title_to_url(genus)
        # API unreachable or both pages missing: epithet with apostrophe is usually cultivar → use genus
        if "'" in epithet:
            return _wiki_title_to_url(genus)
        return _wiki_title_to_url(species_title)

    sci = plant.get("scientific_name")
    if isinstance(sci, list) and sci and isinstance(sci[0], str) and sci[0].strip():
        title = sci[0].strip()
    else:
        title = (plant.get("common_name") or "Plant").strip()
    # When we only have scientific_name/common_name (no genus/epithet in stored data):
    # try full title first; if it doesn't exist and title has multiple words, try first word (genus-like).
    if title and " " in title:
        if not _wikipedia_page_exists(title):
            first_word = title.split()[0]
            if first_word and _wikipedia_page_exists(first_word):
                return _wiki_title_to_url(first_word)
    return _wiki_title_to_url(title)


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
