"""
Background scheduler that applies schedule rules every minute.
Light: desired brightness is computed from all enabled light rules (last matching rule wins).
Pump: at trigger time turn on for N minutes; track off times and turn off when due.

Server-side overrides (stored in schedule_rules.json):
- light_rules_paused_until / pump_rules_paused_until: skip that rule type until the given time.
- manual_pump_off_at: turn pump off at this time (for manual watering).

All rule times (start_time, end_time, time) are in device local time. Set the Pi's
timezone to America/Chicago (Central) so rules match the times shown in the dashboard.
"""
import logging
from datetime import date, datetime, timedelta
from threading import Thread, Event

from .store import (
    get_all_rules,
    get_light_rules_paused_until,
    get_pump_rules_paused_until,
    get_manual_pump_off_at,
    set_manual_pump_off_at,
)

logger = logging.getLogger(__name__)

# Populated when scheduler starts so we don't import at module level (avoids circular / early hardware init)
_light_control = None
_pump_control = None

# Pump off times: list of (datetime, rule_id) when we should turn pump off
_pump_off_at = []
_pump_off_lock = None


def _get_light_control():
    global _light_control
    if _light_control is None:
        try:
            from app.sensors.light.routes import light_control
            _light_control = light_control
        except Exception as e:
            logger.debug("Light control not available for scheduler: %s", e)
    return _light_control


def _get_pump_control():
    global _pump_control
    if _pump_control is None:
        try:
            from app.sensors.pump.routes import pump_control
            _pump_control = pump_control
        except Exception as e:
            logger.debug("Pump control not available for scheduler: %s", e)
    return _pump_control


def _parse_time(s):
    """Parse 'HH:MM' or 'H:MM' to (hour, minute). Returns None if invalid."""
    if not s or ":" not in s:
        return None
    parts = s.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return (h, m)
    except ValueError:
        pass
    return None


def _time_in_minutes(hm):
    """(hour, minute) -> minutes since midnight."""
    if hm is None:
        return -1
    return hm[0] * 60 + hm[1]


def _current_hm():
    """Current (hour, minute)."""
    now = datetime.now()
    return (now.hour, now.minute)


def _parse_iso(s):
    """Parse ISO datetime string to naive datetime, or None if invalid/None."""
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
    except (ValueError, TypeError):
        return None


def _apply_light_rules(now_hm):
    """Compute desired brightness from all enabled light rules and apply. Last matching rule wins."""
    until = _parse_iso(get_light_rules_paused_until())
    if until is not None and datetime.now() < until:
        return
    rules = get_all_rules()
    light_rules = [r for r in rules if r.get("type") == "light" and r.get("enabled", True) and not r.get("paused", False)]
    if not light_rules:
        return

    now_m = _time_in_minutes(now_hm)
    desired = 0
    # Sort by start so "last matching" is deterministic
    for r in sorted(light_rules, key=lambda x: (x.get("start_time") or "")):
        start = _parse_time(r.get("start_time"))
        end = _parse_time(r.get("end_time")) if r.get("end_time") else None
        brightness = r.get("brightness_pct", 0)
        if start is None:
            continue
        start_m = _time_in_minutes(start)
        if end is not None:
            end_m = _time_in_minutes(end)
            if start_m <= now_m < end_m:
                desired = brightness
        else:
            # "Set and stay": active from start_time onward
            if now_m >= start_m:
                desired = brightness
    control = _get_light_control()
    if control is None:
        return
    try:
        if desired == 0:
            control.off()
        else:
            control.on()
            control.set_brightness(int(desired))
    except Exception as e:
        logger.warning("Scheduler could not set light: %s", e)


def _apply_pump_rules(now_dt, now_hm):
    """Check pump rules for trigger time and scheduled off times."""
    global _pump_off_at
    if _pump_off_lock is not None:
        _pump_off_lock.acquire()
    try:
        # 1) Turn off any pumps that are due
        still_pending = []
        pump = _get_pump_control()
        for off_at, rule_id in _pump_off_at:
            if now_dt >= off_at:
                if pump:
                    try:
                        pump.off()
                        if _app is not None:
                            from app.history import log_pump_event
                            log_pump_event(_app, False, "rule", rule_id=rule_id)
                        logger.info("Scheduler: pump off (rule %s)", rule_id)
                    except Exception as e:
                        logger.warning("Scheduler could not turn pump off: %s", e)
            else:
                still_pending.append((off_at, rule_id))
        _pump_off_at = still_pending
    finally:
        if _pump_off_lock is not None:
            _pump_off_lock.release()

    # 2) If manual pump off time reached, turn pump off and clear
    off_at = _parse_iso(get_manual_pump_off_at())
    if off_at is not None and now_dt >= off_at:
        if pump:
            try:
                pump.off()
                if _app is not None:
                    from app.history import log_pump_event
                    log_pump_event(_app, False, "manual")
                logger.info("Scheduler: pump off (manual watering ended)")
            except Exception as e:
                logger.warning("Scheduler could not turn pump off: %s", e)
        set_manual_pump_off_at(None)

    # 3) Fire pump rules at current time (unless pump rules are paused)
    until = _parse_iso(get_pump_rules_paused_until())
    if until is not None and now_dt < until:
        return
    rules = get_all_rules()
    now_str = "%02d:%02d" % (now_hm[0], now_hm[1])
    pump = _get_pump_control()
    to_add = []
    for r in rules:
        if r.get("type") != "pump" or not r.get("enabled", True) or r.get("paused", False):
            continue
        if r.get("time") != now_str:
            continue
        duration = int(r.get("duration_minutes") or 5)
        if pump:
            try:
                pump.on()
                pump.set_speed(100)
                if _app is not None:
                    from app.history import log_pump_event
                    log_pump_event(_app, True, "rule", rule_id=r.get("id", ""))
                off_at = now_dt + timedelta(minutes=duration)
                to_add.append((off_at, r.get("id", "")))
                logger.info("Scheduler: pump on for %s min (rule %s)", duration, r.get("id"))
            except Exception as e:
                logger.warning("Scheduler could not turn pump on: %s", e)
    if to_add and _pump_off_lock is not None:
        _pump_off_lock.acquire()
        try:
            _pump_off_at.extend(to_add)
        finally:
            _pump_off_lock.release()
    elif to_add:
        _pump_off_at.extend(to_add)


def _tick():
    now_dt = datetime.now()
    now_hm = (now_dt.hour, now_dt.minute)
    _apply_light_rules(now_hm)
    _apply_pump_rules(now_dt, now_hm)


# How often the scheduler runs (seconds). Shorter = quicker reaction when pause expires.
_SCHEDULER_INTERVAL = 15

def _scheduler_loop(stop_event):
    """
    Run every _SCHEDULER_INTERVAL seconds until stop_event is set.
    On startup, runs one tick immediately so after a reboot or power loss the correct
    light state is applied right away (e.g. lights 9AM-4PM: if Pi boots at 10AM, lights
    turn on within a second). Pump rules that were supposed to run while the Pi was off
    are not run retroactively.
    Every other tick runs the Slack threshold alert check.
    """
    tick_count = 0
    try:
        _tick()
        tick_count += 1
        _run_plant_of_the_day_jobs()
    except Exception as e:
        logger.exception("Scheduler initial tick failed: %s", e)
        _notify_scheduler_error(e, "initial tick")
    while not stop_event.wait(timeout=_SCHEDULER_INTERVAL):
        try:
            _tick()
            tick_count += 1
            if _app is not None and tick_count % 2 == 0:
                try:
                    from app.alerts.slack_alerts import run_alert_check
                    run_alert_check(_app)
                except Exception as alert_e:
                    logger.warning("Alert check failed: %s", alert_e)
            # Every 5 minutes (20 * 15s): record sensor snapshot for history
            if _app is not None and tick_count > 0 and tick_count % 20 == 0:
                try:
                    from app.history import record_sensor_snapshot
                    record_sensor_snapshot(_app)
                except Exception as hist_e:
                    logger.warning("History sensor snapshot failed: %s", hist_e)
            _run_plant_of_the_day_jobs()
        except Exception as e:
            logger.exception("Scheduler tick failed: %s", e)
            _notify_scheduler_error(e, "scheduler tick")
            tick_count += 1


def _parse_plant_slack_time(time_str):
    """Parse 'HH:MM' or 'H:MM' to (hour, minute) or None."""
    if not time_str or ":" not in str(time_str):
        return (9, 35)
    parts = str(time_str).strip().split(":", 1)
    if len(parts) != 2:
        return (9, 35)
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return (h, m)
    except (ValueError, TypeError):
        pass
    return (9, 35)


def _run_plant_of_the_day_jobs():
    """At midnight: fetch new plant. At configured time: send Slack. Once per day each."""
    global _last_plant_fetch_date, _last_plant_slack_date
    if _app is None:
        return
    now = datetime.now()
    today = date.today()
    if now.hour == 0 and now.minute < 2:
        if _last_plant_fetch_date != today:
            _last_plant_fetch_date = today
            try:
                from app.plant_of_the_day.fetch import fetch_plant_of_the_day
                fetch_plant_of_the_day(_app)
            except Exception as e:
                logger.warning("Plant of the day fetch failed: %s", e)
    # Plant of the day Slack at configured time (default 09:35)
    with _app.app_context():
        from app.settings.routes import _get_or_create
        row = _get_or_create()
        slack_h, slack_m = _parse_plant_slack_time(getattr(row, "plant_of_the_day_slack_time", "09:35"))
    if now.hour == slack_h and slack_m <= now.minute < slack_m + 2:
        if _last_plant_slack_date != today:
            _last_plant_slack_date = today
            try:
                from app.plant_of_the_day import store as plant_store
                from app.plant_of_the_day.fetch import fetch_plant_of_the_day
                from app.plant_of_the_day.slack_plant import send_plant_of_the_day_slack
                # First run in the morning may have no plant yet (midnight hasn't run); fetch one for today
                if plant_store.get_current_plant(_app) is None:
                    fetch_plant_of_the_day(_app)
                send_plant_of_the_day_slack(_app)
            except Exception as e:
                logger.warning("Plant of the day Slack failed: %s", e)


def _notify_scheduler_error(exc, context):
    """Send Slack runtime error notification if enabled."""
    if _app is None:
        return
    try:
        from app.alerts.slack import send_runtime_error
        send_runtime_error(_app, exc, context)
    except Exception:
        pass


_stop_event = Event()
_thread = None
_app = None
_last_plant_fetch_date = None
_last_plant_slack_date = None


def start_scheduler(app=None):
    """Start the background scheduler thread. Pass Flask app for alert checks and error notifications."""
    global _thread, _pump_off_lock, _app
    if app is not None:
        _app = app
    if _thread is not None and _thread.is_alive():
        return
    try:
        import threading
        _pump_off_lock = threading.Lock()
    except Exception:
        _pump_off_lock = None
    _stop_event.clear()
    _thread = Thread(target=_scheduler_loop, args=(_stop_event,), daemon=True)
    _thread.start()
    logger.info("Schedule scheduler started.")


def stop_scheduler():
    """Signal the scheduler to stop (e.g. for tests)."""
    _stop_event.set()
