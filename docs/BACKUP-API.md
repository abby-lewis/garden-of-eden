# Backup & Restore API (for dashboard / home automation)

The Garden of Eden backend can back up its SQLite database and JSON file state to MongoDB, and restore from that backup. This document describes the HTTP API so your dashboard (or another service) can trigger restore or check status.

## Environment

- **MONGODB_URL** (required for backup/restore): Full MongoDB connection string, including database name. Example: `mongodb://user:pass@host:27017/gardyn_backup`. The app uses the database from the URL and a single collection named `backup`.

## Authentication

All backup endpoints require the same authentication as the rest of the API (e.g. Bearer JWT). Include the auth header as you do for other Gardyn API calls.

## Endpoints

### POST `/backup/restore`

Restores the application from the latest backup stored in MongoDB. **Overwrites** all current SQLite data and JSON file state (settings, auth, schedule rules, plant of the day, alert state, sensor readings, pump events).

**Use case:** Your dashboard can call this when the user requests “restore Gardyn from backup” or when you want to reset this instance from a known-good backup.

**Request:**

- Method: `POST`
- Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`
- Body: none required

**Response (200):**

```json
{
  "success": true,
  "message": "Restore completed.",
  "backup_created_at": "2025-02-20T12:00:00Z"
}
```

**Response (404)** if no backup exists in MongoDB:

```json
{
  "success": false,
  "message": "No backup found in MongoDB."
}
```

**Response (500)** on error:

```json
{
  "success": false,
  "message": "<error details>"
}
```

**Example (curl):**

```bash
curl -X POST "https://your-gardyn-api/backup/restore" \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json"
```

**Example (fetch from dashboard):**

```javascript
const response = await fetch(`${GARDYN_API_URL}/backup/restore`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json",
  },
});
const data = await response.json();
if (data.success) {
  console.log("Restored from", data.backup_created_at);
} else {
  console.error(data.message);
}
```

---

### GET `/backup/status`

Returns whether a backup exists and when it was last updated. Does not modify anything.

**Request:**

- Method: `GET`
- Headers: `Authorization: Bearer <token>`

**Response (200) when a backup exists:**

```json
{
  "available": true,
  "created_at": "2025-02-20T12:00:00Z",
  "last_incremental_at": "2025-02-21T03:00:00Z"
}
```

**Response (200) when no backup exists or MongoDB is unreachable:**

```json
{
  "available": false,
  "message": "No backup in MongoDB."
}
```

Use this to show “Last backup: …” in your dashboard or to decide whether restore is possible.

---

### POST `/backup/run`

Runs a **full** backup to MongoDB and then **audits** that every record in SQLite matches what was written. Intended for manual “Backup now” from the Gardyn Settings UI; your dashboard can call it if you want to trigger a backup remotely.

**Request:**

- Method: `POST`
- Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`

**Response (200):**

```json
{
  "success": true,
  "message": "Backup completed. Audit: all records match.",
  "created_at": "2025-02-20T12:00:00Z",
  "audit": {
    "ok": true,
    "message": "All records match",
    "details": {
      "users": { "local_count": 1, "remote_count": 1, "match": true },
      "sensor_readings": { "local_count": 100, "remote_count": 100, "match": true }
    }
  }
}
```

If the audit finds a mismatch, `audit.ok` is `false` and `message`/`details` describe what differed.

**Response (503)** if MongoDB is not available:

```json
{
  "success": false,
  "message": "MongoDB not available: ..."
}
```

---

## Behavior summary

| Action        | When to use it                         |
|---------------|----------------------------------------|
| **Backup**    | Manual “Backup to MongoDB” in Settings or from your dashboard. |
| **Restore**   | Manual “Restore from MongoDB” in Settings or **from your dashboard** (e.g. “Restore Gardyn” button). |
| **Status**    | To show “Last backup: …” or to enable/disable a “Restore” button. |

- A **full backup** runs when the user clicks “Backup to MongoDB” (or when you call `POST /backup/run`). It exports all data and runs an audit.
- An **incremental backup** runs automatically every day at **3:00 AM** (device local time). It adds only new sensor readings and pump events from the last 24 hours (and refreshes settings/auth/files) so the MongoDB snapshot stays up to date without re-uploading everything.

You can rely on `POST /backup/restore` for your dashboard “restore” flow: it always restores from the latest snapshot in MongoDB (full + any incremental updates).
