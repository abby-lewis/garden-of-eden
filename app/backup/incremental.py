"""
Incremental backup: merge new data from the last 24 hours (or since last run) into MongoDB.
Called daily at 3 AM by the scheduler.
"""
import logging
from datetime import datetime, timezone, timedelta

if False:
    from flask import Flask

logger = logging.getLogger(__name__)


def run_incremental_backup(app: "Flask") -> None:
    """
    Export new sensor_readings and pump_events since last_incremental_at (or 24h ago),
    merge into the backup document in MongoDB, update last_incremental_at.
    If no backup exists, do a full backup instead.
    """
    with app.app_context():
        from app.backup.mongodb import get_backup_doc, put_backup_doc, get_client
        from app.backup.export_import import export_snapshot

        try:
            get_client()
        except Exception as e:
            logger.warning("Incremental backup skipped (MongoDB): %s", e)
            return

        doc = get_backup_doc()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        if not doc or "data" not in doc:
            # No existing backup: do full backup
            logger.info("No existing backup; performing full backup.")
            snapshot = export_snapshot(app)
            created_at = now.isoformat().replace("+00:00", "Z")
            put_backup_doc(snapshot, created_at, last_incremental_at=created_at)
            return

        last_ts = doc.get("last_incremental_at") or doc.get("created_at")
        try:
            if isinstance(last_ts, str):
                last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            else:
                last_dt = cutoff
        except Exception:
            last_dt = cutoff
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        # Use the more recent of (last_incremental_at, 24h ago) so we don't miss data
        since = max(last_dt, cutoff, key=lambda t: t.timestamp())
        since_naive = since.replace(tzinfo=None)

        from app.models import SensorReading, PumpEvent
        from app.backup.export_import import _serialize_dt

        new_readings = [
            {
                "id": r.id,
                "created_at": _serialize_dt(r.created_at),
                "water_level": r.water_level,
                "humidity": r.humidity,
                "air_temp": r.air_temp,
                "pcb_temp": r.pcb_temp,
                "light_percentage": r.light_percentage,
            }
            for r in SensorReading.query.filter(SensorReading.created_at >= since_naive).order_by(SensorReading.id).all()
        ]
        new_events = [
            {
                "id": e.id,
                "created_at": _serialize_dt(e.created_at),
                "is_on": e.is_on,
                "trigger": e.trigger,
                "rule_id": e.rule_id,
            }
            for e in PumpEvent.query.filter(PumpEvent.created_at >= since_naive).order_by(PumpEvent.id).all()
        ]

        existing_data = doc.get("data", {})
        existing_readings = list(existing_data.get("sensor_readings", []))
        existing_events = list(existing_data.get("pump_events", []))
        existing_ids_r = {r["id"] for r in existing_readings}
        existing_ids_e = {e["id"] for e in existing_events}
        for r in new_readings:
            if r["id"] not in existing_ids_r:
                existing_readings.append(r)
                existing_ids_r.add(r["id"])
        for e in new_events:
            if e["id"] not in existing_ids_e:
                existing_events.append(e)
                existing_ids_e.add(e["id"])

        # Full export for small tables and files (so settings/auth/plant/rules stay current)
        full = export_snapshot(app)
        merged_data = full["data"]
        merged_data["sensor_readings"] = existing_readings
        merged_data["pump_events"] = existing_events
        snapshot = {"data": merged_data, "files": full["files"]}

        created_at = doc.get("created_at")
        last_incremental_at = now.isoformat().replace("+00:00", "Z")
        put_backup_doc(snapshot, created_at, last_incremental_at=last_incremental_at)
        logger.info("Incremental backup done: +%d readings, +%d events.", len(new_readings), len(new_events))
