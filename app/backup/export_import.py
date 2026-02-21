"""
Export SQLite tables + JSON file state to a snapshot dict.
Import snapshot back to SQLite + files.
"""
import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path

if False:
    from flask import Flask

logger = logging.getLogger(__name__)


def _serialize_dt(dt):
    if dt is None:
        return None
    return dt.isoformat() + ("Z" if dt.tzinfo is None else "")


def _deserialize_dt(s):
    if s is None:
        return None
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _bytes_to_b64(b):
    if b is None:
        return None
    return base64.b64encode(b).decode("ascii")


def _b64_to_bytes(s):
    if s is None:
        return None
    return base64.b64decode(s)


def export_snapshot(app: "Flask") -> dict:
    """Export all backupable data from SQLite and JSON files. Returns JSON-serializable dict."""
    with app.app_context():
        from app.models import (
            db,
            User,
            WebAuthnCredential,
            AppSettings,
            SensorReading,
            PumpEvent,
        )
        from app.schedules.store import load_rules
        from app.plant_of_the_day import store as plant_store
        from app.alerts.alert_state import _load as alert_load, _save as alert_save

        data = {}

        # Users
        users = User.query.all()
        data["users"] = [
            {
                "id": u.id,
                "name": u.name,
                "display_name": u.display_name,
                "email": u.email,
            }
            for u in users
        ]

        # WebAuthn credentials (bytes -> b64)
        creds = WebAuthnCredential.query.all()
        data["webauthn_credentials"] = [
            {
                "id": c.id,
                "user_id": c.user_id,
                "credential_id": _bytes_to_b64(c.credential_id),
                "public_key": _bytes_to_b64(c.public_key),
                "sign_count": c.sign_count,
            }
            for c in creds
        ]

        # App settings (single row id=1)
        row = AppSettings.query.get(1)
        data["app_settings"] = [row.to_dict()] if row else []

        # Sensor readings
        readings = SensorReading.query.order_by(SensorReading.id.asc()).all()
        data["sensor_readings"] = [
            {
                "id": r.id,
                "created_at": _serialize_dt(r.created_at),
                "water_level": r.water_level,
                "humidity": r.humidity,
                "air_temp": r.air_temp,
                "pcb_temp": r.pcb_temp,
                "light_percentage": r.light_percentage,
            }
            for r in readings
        ]

        # Pump events
        events = PumpEvent.query.order_by(PumpEvent.id.asc()).all()
        data["pump_events"] = [
            {
                "id": e.id,
                "created_at": _serialize_dt(e.created_at),
                "is_on": e.is_on,
                "trigger": e.trigger,
                "rule_id": e.rule_id,
            }
            for e in events
        ]

        files = {}

        # Schedule rules (JSON file)
        try:
            files["schedule_rules"] = load_rules()
        except Exception as e:
            logger.warning("Export schedule_rules: %s", e)
            files["schedule_rules"] = {"rules": [], "light_rules_paused_until": None, "pump_rules_paused_until": None, "manual_pump_off_at": None}

        # Plant of the day
        try:
            plant = plant_store.get_current_plant(app)
            files["plant_of_the_day_current"] = plant
            ids = plant_store.get_used_ids(app)
            files["plant_of_the_day_used_ids"] = {"ids": list(ids)}
        except Exception as e:
            logger.warning("Export plant_of_the_day: %s", e)
            files["plant_of_the_day_current"] = None
            files["plant_of_the_day_used_ids"] = {"ids": []}

        # Alert state
        try:
            files["alert_state"] = alert_load(app)
        except Exception as e:
            logger.warning("Export alert_state: %s", e)
            files["alert_state"] = {}

        return {"data": data, "files": files}


def import_snapshot(app: "Flask", snapshot: dict) -> None:
    """Overwrite SQLite tables and JSON files with the given snapshot."""
    with app.app_context():
        from app.models import (
            db,
            User,
            WebAuthnCredential,
            AppSettings,
            SensorReading,
            PumpEvent,
        )
        from app.schedules.store import save_rules
        from app.plant_of_the_day import store as plant_store
        from app.alerts.alert_state import _state_path, _save as alert_save

        data = snapshot.get("data", {})
        files = snapshot.get("files", {})

        # Clear and re-insert in dependency order
        PumpEvent.query.delete()
        SensorReading.query.delete()
        WebAuthnCredential.query.delete()
        User.query.delete()
        AppSettings.query.delete()
        db.session.commit()

        # Users
        for row in data.get("users", []):
            u = User(
                id=row["id"],
                name=row["name"],
                display_name=row.get("display_name", ""),
                email=row.get("email"),
            )
            db.session.add(u)
        db.session.commit()

        # WebAuthn credentials
        for row in data.get("webauthn_credentials", []):
            c = WebAuthnCredential(
                id=row["id"],
                user_id=row["user_id"],
                credential_id=_b64_to_bytes(row["credential_id"]),
                public_key=_b64_to_bytes(row["public_key"]),
                sign_count=row.get("sign_count", 0),
            )
            db.session.add(c)
        db.session.commit()

        # App settings (id=1)
        for row in data.get("app_settings", []):
            # Build kwargs from to_dict shape; id is always 1
            kwargs = {k: v for k, v in row.items()}
            kwargs["id"] = 1
            s = AppSettings(**kwargs)
            db.session.add(s)
        db.session.commit()

        # Sensor readings
        for row in data.get("sensor_readings", []):
            r = SensorReading(
                id=row["id"],
                created_at=_deserialize_dt(row["created_at"]),
                water_level=row.get("water_level"),
                humidity=row.get("humidity"),
                air_temp=row.get("air_temp"),
                pcb_temp=row.get("pcb_temp"),
                light_percentage=row.get("light_percentage"),
            )
            db.session.add(r)
        db.session.commit()

        # Pump events
        for row in data.get("pump_events", []):
            e = PumpEvent(
                id=row["id"],
                created_at=_deserialize_dt(row["created_at"]),
                is_on=row["is_on"],
                trigger=row["trigger"],
                rule_id=row.get("rule_id"),
            )
            db.session.add(e)
        db.session.commit()

        # Schedule rules file
        if "schedule_rules" in files:
            try:
                save_rules(files["schedule_rules"])
            except Exception as e:
                logger.warning("Restore schedule_rules: %s", e)

        # Plant of the day files
        if files.get("plant_of_the_day_current"):
            try:
                plant_store.set_current_plant(app, files["plant_of_the_day_current"])
            except Exception as e:
                logger.warning("Restore plant_of_the_day_current: %s", e)
        if "plant_of_the_day_used_ids" in files:
            try:
                path = Path(app.instance_path) / plant_store.USED_IDS_FILENAME
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w") as f:
                    json.dump(files["plant_of_the_day_used_ids"], f)
            except Exception as e:
                logger.warning("Restore plant_of_the_day_used_ids: %s", e)

        # Alert state file
        if "alert_state" in files:
            try:
                alert_save(app, files["alert_state"])
            except Exception as e:
                logger.warning("Restore alert_state: %s", e)

        # Reset SQLite sequences so new rows get ids after restored max id
        from sqlalchemy import text
        for table, col in [("users", "id"), ("webauthn_credentials", "id"), ("sensor_readings", "id"), ("pump_events", "id")]:
            try:
                r = db.session.execute(text(f"SELECT COALESCE(MAX({col}), 0) FROM {table}"))
                max_id = r.scalar() or 0
                db.session.execute(text(f"DELETE FROM sqlite_sequence WHERE name = :name"), {"name": table})
                db.session.execute(text(f"INSERT INTO sqlite_sequence (name, seq) VALUES (:name, :seq)"), {"name": table, "seq": max_id})
                db.session.commit()
            except Exception as e:
                logger.warning("Reset sequence for %s: %s", table, e)
