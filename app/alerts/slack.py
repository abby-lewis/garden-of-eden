"""
Send messages to Slack via Incoming Webhook.
URL: from AppSettings.slack_webhook_url (if set) else SLACK_WEBHOOK_URL env.
"""
import json
import logging
import os
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def get_webhook_url(app):
    """Return webhook URL from settings (if set and non-empty) else from env."""
    with app.app_context():
        from app.models import AppSettings
        from app.settings.routes import _get_or_create
        row = _get_or_create()
        url = (row.slack_webhook_url or "").strip() if getattr(row, "slack_webhook_url", None) else None
        if url:
            return url
    return (os.environ.get("SLACK_WEBHOOK_URL") or "").strip() or None


def send_slack(app, text):
    """
    POST text to Slack. No-op if Slack is disabled or no webhook URL.
    Does not raise; logs on failure.
    """
    with app.app_context():
        from app.models import AppSettings
        from app.settings.routes import _get_or_create
        row = _get_or_create()
        if not getattr(row, "slack_notifications_enabled", True):
            return
    url = get_webhook_url(app)
    if not url:
        logger.debug("Slack webhook URL not set; skipping message.")
        return
    try:
        body = {"text": text}
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 201, 204):
                logger.warning("Slack webhook returned %s", resp.status)
    except urllib.error.HTTPError as e:
        logger.warning("Slack webhook HTTP error: %s %s", e.code, e.reason)
    except urllib.error.URLError as e:
        logger.warning("Slack webhook URL error: %s", e.reason)
    except Exception as e:
        logger.warning("Slack send failed: %s", e)


def send_test_slack(app, webhook_url_override=None):
    """
    Send a test message to Slack.
    Uses webhook_url_override if non-empty, else current webhook from settings or env.
    Raises ValueError if no webhook URL. Raises RuntimeError on send failure.
    """
    url = (webhook_url_override or "").strip() or get_webhook_url(app)
    if not url:
        raise ValueError("No Slack webhook URL configured. Set it in Settings or SLACK_WEBHOOK_URL env.")
    text = (
        "🧪 *Gardyn – Test notification*\n"
        "If you see this, Slack notifications are working."
    )
    try:
        body = {"text": text}
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"Slack webhook returned status {resp.status}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Slack webhook error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Slack webhook error: {e.reason}")


def send_runtime_error(app, exc, context="Server"):
    """
    Send a runtime error notification to Slack if enabled in settings.
    Message is informative and uses emojis.
    """
    with app.app_context():
        from app.settings.routes import _get_or_create
        row = _get_or_create()
        if not getattr(row, "slack_notifications_enabled", True):
            return
        if not getattr(row, "slack_runtime_errors_enabled", False):
            return
    url = get_webhook_url(app)
    if not url:
        return
    exc_type = type(exc).__name__
    exc_msg = str(exc) or "(no message)"
    text = (
        f"🚨 *Gardyn server error*\n"
        f"*Context:* {context}\n"
        f"*Type:* `{exc_type}`\n"
        f"*Message:* {exc_msg}\n"
        f"Check server logs for full traceback."
    )
    try:
        body = {"text": text}
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        logger.warning("Failed to send Slack runtime error notification: %s", e)
