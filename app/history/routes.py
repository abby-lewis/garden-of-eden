"""
API for historical sensor readings and pump events.
"""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify

from app.models import SensorReading, PumpEvent, db

history_blueprint = Blueprint("history", __name__)

ALLOWED_METRICS = {"water_level", "humidity", "air_temp", "pcb_temp", "light_percentage"}
RANGE_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def _parse_range() -> tuple[datetime, datetime] | None:
    range_name = (request.args.get("range") or "").strip().lower()
    if range_name not in RANGE_DAYS:
        return None
    days = RANGE_DAYS[range_name]
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    return (start, now)


@history_blueprint.route("/readings", methods=["GET"])
def get_readings():
    """
    GET /history/readings?metrics=water_level,humidity,air_temp,pcb_temp,light_percentage&range=day|week|month|year
    Returns { data: [ { created_at: "ISO8601", water_level?, humidity?, ... }, ... ] } in ascending time.
    """
    range_pair = _parse_range()
    if range_pair is None:
        return jsonify({"error": "Missing or invalid query param: range (day|week|month|year)"}), 400
    start, end = range_pair

    metrics_param = (request.args.get("metrics") or "").strip()
    if not metrics_param:
        return jsonify({"error": "Missing query param: metrics (comma-separated)"}), 400
    metrics = [m.strip() for m in metrics_param.split(",") if m.strip()]
    invalid = [m for m in metrics if m not in ALLOWED_METRICS]
    if invalid:
        return jsonify({"error": f"Invalid metric(s): {invalid}. Allowed: {list(ALLOWED_METRICS)}"}), 400

    # SensorReading has created_at in UTC (we store with default=datetime.utcnow)
    # Compare naive UTC with aware start/end by making start/end naive UTC
    start_naive = start.replace(tzinfo=None) if start.tzinfo else start
    end_naive = end.replace(tzinfo=None) if end.tzinfo else end

    rows = (
        db.session.query(SensorReading)
        .filter(SensorReading.created_at >= start_naive, SensorReading.created_at <= end_naive)
        .order_by(SensorReading.created_at.asc())
        .all()
    )

    data = []
    for r in rows:
        point = {"created_at": r.created_at.isoformat() + "Z"}
        for m in metrics:
            val = getattr(r, m, None)
            if val is not None:
                point[m] = round(float(val), 2)
        data.append(point)

    return jsonify({"data": data})


@history_blueprint.route("/pump-events", methods=["GET"])
def get_pump_events():
    """
    GET /history/pump-events?range=day|week|month|year
    Returns { events: [ { created_at, is_on, trigger, rule_id? }, ... ] } ascending.
    """
    range_pair = _parse_range()
    if range_pair is None:
        return jsonify({"error": "Missing or invalid query param: range (day|week|month|year)"}), 400
    start, end = range_pair

    start_naive = start.replace(tzinfo=None) if start.tzinfo else start
    end_naive = end.replace(tzinfo=None) if end.tzinfo else end

    rows = (
        db.session.query(PumpEvent)
        .filter(PumpEvent.created_at >= start_naive, PumpEvent.created_at <= end_naive)
        .order_by(PumpEvent.created_at.asc())
        .all()
    )

    events = [
        {
            "created_at": r.created_at.isoformat() + "Z",
            "is_on": r.is_on,
            "trigger": r.trigger,
            "rule_id": r.rule_id,
        }
        for r in rows
    ]
    return jsonify({"events": events})
