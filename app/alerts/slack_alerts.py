"""
Threshold alert check: read sensors, compare to settings, send Slack on transition to alarm or recovery.
Respects per-category enabled flags and cooldown.
"""
import logging
from datetime import datetime

from . import alert_state
from . import slack

logger = logging.getLogger(__name__)


def _read_sensors(app):
    """Return (water_distance_cm, air_temp_f, humidity_pct, pcb_temp_f). None for any read failure."""
    water_cm = None
    air_temp_f = None
    humidity_pct = None
    pcb_temp_f = None

    try:
        from app.sensors.distance.routes import distance_control
        water_cm = distance_control.measure_once()
    except Exception as e:
        logger.debug("Alert check: distance read failed: %s", e)

    try:
        from app.sensors.temperature.routes import temperature_sensor
        if temperature_sensor is not None:
            t_c = temperature_sensor.read()
            if t_c is not None:
                air_temp_f = t_c * 9 / 5 + 32
    except Exception as e:
        logger.debug("Alert check: temperature read failed: %s", e)

    try:
        from app.sensors.humidity.routes import humidity_sensor
        if humidity_sensor is not None:
            humidity_pct = humidity_sensor.read()
    except Exception as e:
        logger.debug("Alert check: humidity read failed: %s", e)

    try:
        from app.sensors.pcb_temp.pcb_temp import get_pcb_temperature
        t_c = get_pcb_temperature()
        if t_c is not None:
            pcb_temp_f = t_c * 9 / 5 + 32
    except Exception as e:
        logger.debug("Alert check: pcb temp read failed: %s", e)

    return water_cm, air_temp_f, humidity_pct, pcb_temp_f


def run_alert_check(app):
    """
    Run threshold checks and send Slack alerts/recoveries.
    Only sends when Slack notifications are enabled and webhook is set.
    Uses cooldown and transition logic (alert on OK->breach, recovery on breach->OK).
    """
    # Load settings from database (single source of truth for thresholds and toggles)
    with app.app_context():
        from app.settings.routes import _get_or_create
        row = _get_or_create()
        if not getattr(row, "slack_notifications_enabled", True):
            return
        cooldown = max(1, min(120, getattr(row, "slack_cooldown_minutes", 15)))
    water_cm, air_temp_f, humidity_pct, pcb_temp_f = _read_sensors(app)

    # Thresholds and enabled flags from DB (row from _get_or_create())
    with app.app_context():
        from app.settings.routes import _get_or_create
        row = _get_or_create()

    def check(key, in_alarm, enabled, send_alert_fn, send_recovery_fn):
        if not enabled:
            return
        state = alert_state.get_state(app, key)
        was_in_alarm = state["in_alarm"]
        if in_alarm and not was_in_alarm:
            if alert_state.can_send_alert(app, key, cooldown):
                send_alert_fn()
                alert_state.set_alarm_sent(app, key)
            else:
                alert_state.set_in_alarm(app, key, True)
        elif not in_alarm and was_in_alarm:
            if alert_state.can_send_recovery(app, key, cooldown):
                send_recovery_fn()
                alert_state.set_recovery_sent(app, key)

    # Water level (low = distance >= threshold); thresholds from DB row
    water_enabled = getattr(row, "water_level_alerts_enabled", False)
    water_thresh = getattr(row, "water_alert_threshold", 12.0)
    water_low = water_cm is not None and water_cm >= water_thresh
    def send_water_alert():
        slack.send_slack(app, f"💧 *Gardyn – Water level low*\nCurrent: {water_cm:.1f} cm (threshold: {water_thresh} cm). Consider refilling.")
    def send_water_recovery():
        slack.send_slack(app, f"✅ *Gardyn – Water level OK*\nBack to normal ({water_cm:.1f} cm).")
    check("water_low", water_low, water_enabled, send_water_alert, send_water_recovery)

    # Air temp (thresholds from DB row)
    air_enabled = getattr(row, "air_temp_alerts_enabled", False)
    air_high_thresh = getattr(row, "air_temp_high_alert_threshold", 80.0)
    air_low_thresh = getattr(row, "air_temp_low_alert_threshold", 65.0)
    air_high = air_temp_f is not None and air_temp_f > air_high_thresh
    air_low = air_temp_f is not None and air_temp_f < air_low_thresh
    def send_air_high():
        slack.send_slack(app, f"🌡️ *Gardyn – Air temperature high*\nCurrent: {air_temp_f:.1f}°F (threshold: {air_high_thresh}°F).")
    def send_air_high_recovery():
        slack.send_slack(app, f"✅ *Gardyn – Air temperature OK*\nBack to normal ({air_temp_f:.1f}°F).")
    def send_air_low():
        slack.send_slack(app, f"🥶 *Gardyn – Air temperature low*\nCurrent: {air_temp_f:.1f}°F (threshold: {air_low_thresh}°F).")
    def send_air_low_recovery():
        slack.send_slack(app, f"✅ *Gardyn – Air temperature OK*\nBack to normal ({air_temp_f:.1f}°F).")
    check("air_temp_high", air_high, air_enabled, send_air_high, send_air_high_recovery)
    check("air_temp_low", air_low, air_enabled, send_air_low, send_air_low_recovery)

    # Humidity (thresholds from DB row)
    hum_enabled = getattr(row, "humidity_alerts_enabled", False)
    hum_low_thresh = getattr(row, "humidity_low_alert_threshold", 40.0)
    hum_high_thresh = getattr(row, "humidity_high_alert_threshold", 90.0)
    hum_low = humidity_pct is not None and humidity_pct < hum_low_thresh
    hum_high = humidity_pct is not None and humidity_pct > hum_high_thresh
    def send_hum_low():
        slack.send_slack(app, f"💨 *Gardyn – Humidity low*\nCurrent: {humidity_pct:.1f}% (threshold: {hum_low_thresh}%).")
    def send_hum_low_recovery():
        slack.send_slack(app, f"✅ *Gardyn – Humidity OK*\nBack to normal ({humidity_pct:.1f}%).")
    def send_hum_high():
        slack.send_slack(app, f"💦 *Gardyn – Humidity high*\nCurrent: {humidity_pct:.1f}% (threshold: {hum_high_thresh}%).")
    def send_hum_high_recovery():
        slack.send_slack(app, f"✅ *Gardyn – Humidity OK*\nBack to normal ({humidity_pct:.1f}%).")
    check("humidity_low", hum_low, hum_enabled, send_hum_low, send_hum_low_recovery)
    check("humidity_high", hum_high, hum_enabled, send_hum_high, send_hum_high_recovery)

    # PCB temp (threshold from DB row)
    pcb_enabled = getattr(row, "pcb_temp_alerts_enabled", False)
    pcb_thresh = getattr(row, "pcb_temp_alert_threshold", 110.0)
    pcb_high = pcb_temp_f is not None and pcb_temp_f > pcb_thresh
    def send_pcb_alert():
        slack.send_slack(app, f"🔥 *Gardyn – PCB temperature high*\nCurrent: {pcb_temp_f:.1f}°F (threshold: {pcb_thresh}°F). Check ventilation.")
    def send_pcb_recovery():
        slack.send_slack(app, f"✅ *Gardyn – PCB temperature OK*\nBack to normal ({pcb_temp_f:.1f}°F).")
    check("pcb_temp_high", pcb_high, pcb_enabled, send_pcb_alert, send_pcb_recovery)
