"""
Audit: compare current SQLite + files state to a backup snapshot.
Returns a report indicating whether every record matches.
"""
import json
import logging
from datetime import datetime

if False:
    from flask import Flask

logger = logging.getLogger(__name__)


def _serialize_dt(dt):
    if dt is None:
        return None
    return dt.isoformat() + ("Z" if dt.tzinfo is None else "")


def _bytes_b64(b):
    if b is None:
        return None
    import base64
    return base64.b64encode(b).decode("ascii")


def audit_snapshot(app: "Flask", snapshot: dict) -> dict:
    """
    Compare current DB and files to the given snapshot.
    Returns { "ok": bool, "message": str, "details": { table: { "local_count": n, "remote_count": n, "match": bool }, ... } }.
    """
    with app.app_context():
        from app.models import (
            User,
            WebAuthnCredential,
            AppSettings,
            SensorReading,
            PumpEvent,
        )
        from app.schedules.store import load_rules
        from app.plant_of_the_day import store as plant_store
        from app.alerts.alert_state import _load as alert_load

        data = snapshot.get("data", {})
        files = snapshot.get("files", {})
        details = {}
        all_ok = True

        def _seq_match(local_list, remote_list, key_fn=lambda x: x.get("id")):
            if len(local_list) != len(remote_list):
                return False
            local_by_key = {key_fn(r): r for r in local_list}
            remote_by_key = {key_fn(r): r for r in remote_list}
            if set(local_by_key) != set(remote_by_key):
                return False
            for k, r in remote_by_key.items():
                l = local_by_key.get(k)
                if l != r:
                    return False
            return True

        # Users
        local_users = [
            {"id": u.id, "name": u.name, "display_name": u.display_name, "email": u.email}
            for u in User.query.all()
        ]
        remote_users = data.get("users", [])
        users_match = _seq_match(local_users, remote_users)
        details["users"] = {"local_count": len(local_users), "remote_count": len(remote_users), "match": users_match}
        if not users_match:
            all_ok = False

        # WebAuthn credentials (compare with b64 credential_id for consistency)
        local_creds = [
            {
                "id": c.id,
                "user_id": c.user_id,
                "credential_id": _bytes_b64(c.credential_id),
                "public_key": _bytes_b64(c.public_key),
                "sign_count": c.sign_count,
            }
            for c in WebAuthnCredential.query.all()
        ]
        remote_creds = data.get("webauthn_credentials", [])
        creds_match = _seq_match(local_creds, remote_creds)
        details["webauthn_credentials"] = {"local_count": len(local_creds), "remote_count": len(remote_creds), "match": creds_match}
        if not creds_match:
            all_ok = False

        # App settings
        row = AppSettings.query.get(1)
        local_settings = [row.to_dict()] if row else []
        remote_settings = data.get("app_settings", [])
        settings_match = _seq_match(local_settings, remote_settings) or (len(local_settings) == 0 and len(remote_settings) == 0)
        details["app_settings"] = {"local_count": len(local_settings), "remote_count": len(remote_settings), "match": settings_match}
        if not settings_match:
            all_ok = False

        # Sensor readings
        local_readings = [
            {
                "id": r.id,
                "created_at": _serialize_dt(r.created_at),
                "water_level": r.water_level,
                "humidity": r.humidity,
                "air_temp": r.air_temp,
                "pcb_temp": r.pcb_temp,
                "light_percentage": r.light_percentage,
            }
            for r in SensorReading.query.order_by(SensorReading.id).all()
        ]
        remote_readings = data.get("sensor_readings", [])
        readings_match = _seq_match(local_readings, remote_readings)
        details["sensor_readings"] = {"local_count": len(local_readings), "remote_count": len(remote_readings), "match": readings_match}
        if not readings_match:
            all_ok = False

        # Pump events
        local_events = [
            {
                "id": e.id,
                "created_at": _serialize_dt(e.created_at),
                "is_on": e.is_on,
                "trigger": e.trigger,
                "rule_id": e.rule_id,
            }
            for e in PumpEvent.query.order_by(PumpEvent.id).all()
        ]
        remote_events = data.get("pump_events", [])
        events_match = _seq_match(local_events, remote_events)
        details["pump_events"] = {"local_count": len(local_events), "remote_count": len(remote_events), "match": events_match}
        if not events_match:
            all_ok = False

        # Files: schedule_rules, plant_of_the_day, alert_state (compare as dicts)
        try:
            local_rules = load_rules()
            remote_rules = files.get("schedule_rules") or {}
            rules_match = local_rules.get("rules") == remote_rules.get("rules") and (
                local_rules.get("light_rules_paused_until") == remote_rules.get("light_rules_paused_until") and
                local_rules.get("pump_rules_paused_until") == remote_rules.get("pump_rules_paused_until") and
                local_rules.get("manual_pump_off_at") == remote_rules.get("manual_pump_off_at")
            )
        except Exception:
            rules_match = False
        details["schedule_rules"] = {"match": rules_match}
        if not rules_match:
            all_ok = False

        try:
            local_plant = plant_store.get_current_plant(app)
            remote_plant = files.get("plant_of_the_day_current")
            plant_match = (local_plant is None and remote_plant is None) or (local_plant == remote_plant)
            local_ids = plant_store.get_used_ids(app)
            remote_ids = set((files.get("plant_of_the_day_used_ids") or {}).get("ids", []))
            ids_match = local_ids == remote_ids
        except Exception:
            plant_match = ids_match = False
        details["plant_of_the_day"] = {"current_match": plant_match, "used_ids_match": ids_match}
        if not (plant_match and ids_match):
            all_ok = False

        try:
            local_alert = alert_load(app)
            remote_alert = files.get("alert_state") or {}
            alert_match = local_alert == remote_alert
        except Exception:
            alert_match = False
        details["alert_state"] = {"match": alert_match}
        if not alert_match:
            all_ok = False

        return {
            "ok": all_ok,
            "message": "All records match" if all_ok else "One or more tables or files do not match",
            "details": details,
        }
