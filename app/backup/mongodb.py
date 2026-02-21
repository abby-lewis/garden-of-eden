"""
MongoDB connection and backup document access.
Uses MONGODB_URL env (database name is in the URL; we use collection 'backup').
"""
import logging
import os

logger = logging.getLogger(__name__)

COLLECTION_NAME = "backup"
DOC_ID = "latest"

_client = None


def get_client():
    """Return pymongo MongoClient. Raises if MONGODB_URL not set or invalid."""
    global _client
    if _client is not None:
        return _client
    url = (os.environ.get("MONGODB_URL") or "").strip()
    if not url:
        raise ValueError("MONGODB_URL is not set")
    try:
        from pymongo import MongoClient
        _client = MongoClient(url, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        return _client
    except Exception as e:
        logger.warning("MongoDB connection failed: %s", e)
        raise


def get_collection():
    """Return the backup collection (database is inferred from MONGODB_URL)."""
    client = get_client()
    # Default database from URL (e.g. mongodb://host/dbname -> dbname)
    db = client.get_database()
    return db[COLLECTION_NAME]


def get_backup_doc():
    """Return the current backup document or None."""
    try:
        coll = get_collection()
        return coll.find_one({"_id": DOC_ID})
    except Exception as e:
        logger.warning("Could not read backup document: %s", e)
        return None


def put_backup_doc(snapshot: dict, created_at: str, last_incremental_at: str | None = None):
    """Replace the backup document with the given snapshot."""
    coll = get_collection()
    doc = {
        "_id": DOC_ID,
        "created_at": created_at,
        "data": snapshot.get("data", {}),
        "files": snapshot.get("files", {}),
    }
    if last_incremental_at is not None:
        doc["last_incremental_at"] = last_incremental_at
    coll.replace_one({"_id": DOC_ID}, doc, upsert=True)


def update_backup_meta(last_incremental_at: str):
    """Update only last_incremental_at on the backup document."""
    coll = get_collection()
    coll.update_one(
        {"_id": DOC_ID},
        {"$set": {"last_incremental_at": last_incremental_at}},
        upsert=False,
    )
