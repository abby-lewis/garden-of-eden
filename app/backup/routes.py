"""
Backup and restore API. Requires auth.
POST /backup/run   - Manual full backup to MongoDB, then audit.
POST /backup/restore - Restore from MongoDB (latest snapshot).
GET  /backup/status - Last backup time and optional audit summary.
"""
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, current_app

from app.backup.export_import import export_snapshot, import_snapshot
from app.backup.mongodb import get_backup_doc, put_backup_doc, get_client
from app.backup.audit import audit_snapshot

logger = logging.getLogger(__name__)

backup_blueprint = Blueprint("backup", __name__)


@backup_blueprint.route("/run", methods=["POST"])
def run_backup():
    """
    Perform a full backup to MongoDB, then audit that SQLite matches MongoDB.
    Returns { success, message, audit: { ok, message, details } }.
    """
    try:
        get_client()
    except Exception as e:
        return jsonify({"success": False, "message": f"MongoDB not available: {e}"}), 503

    try:
        snapshot = export_snapshot(current_app)
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        put_backup_doc(snapshot, created_at)
        audit_result = audit_snapshot(current_app, snapshot)
        return jsonify({
            "success": True,
            "message": "Backup completed. Audit: " + ("all records match." if audit_result["ok"] else "mismatch (see audit.details)."),
            "created_at": created_at,
            "audit": audit_result,
        })
    except Exception as e:
        logger.exception("Backup failed: %s", e)
        return jsonify({"success": False, "message": str(e)}), 500


@backup_blueprint.route("/restore", methods=["POST"])
def restore_backup():
    """
    Restore from the latest backup in MongoDB.
    Overwrites SQLite and JSON file state. Returns { success, message }.
    """
    try:
        doc = get_backup_doc()
        if not doc or "data" not in doc:
            return jsonify({"success": False, "message": "No backup found in MongoDB."}), 404

        snapshot = {"data": doc["data"], "files": doc.get("files", {})}
        import_snapshot(current_app, snapshot)
        return jsonify({
            "success": True,
            "message": "Restore completed.",
            "backup_created_at": doc.get("created_at"),
        })
    except Exception as e:
        logger.exception("Restore failed: %s", e)
        return jsonify({"success": False, "message": str(e)}), 500


@backup_blueprint.route("/status", methods=["GET"])
def backup_status():
    """Return last backup time and whether MongoDB is reachable."""
    try:
        doc = get_backup_doc()
        if not doc:
            return jsonify({"available": False, "message": "No backup in MongoDB."})
        return jsonify({
            "available": True,
            "created_at": doc.get("created_at"),
            "last_incremental_at": doc.get("last_incremental_at"),
        })
    except Exception as e:
        return jsonify({"available": False, "message": str(e)})
