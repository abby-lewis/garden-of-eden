"""
Record sensor snapshots (for 5-min polling) and pump on/off events.
Uses lazy imports to avoid circular imports and early hardware init.
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)


def record_sensor_snapshot(app: "Flask") -> None:
    """
    Read current sensor values and light percentage, then insert one row into sensor_readings.
    Called every 5 minutes from the scheduler. Ignores per-sensor errors and stores what we can.
    """
    with app.app_context():
        from app.models import SensorReading, db

        water_level = None
        humidity = None
        air_temp = None
        pcb_temp = None
        light_percentage = None

        try:
            from app.sensors.distance.routes import distance_control
            water_level = float(distance_control.measure_once())
        except Exception as e:
            logger.debug("History: skip water_level: %s", e)

        try:
            from app.sensors.humidity.routes import humidity_sensor
            humidity = float(humidity_sensor.read())
        except Exception as e:
            logger.debug("History: skip humidity: %s", e)

        try:
            from app.sensors.temperature.routes import temperature_sensor
            air_temp = float(temperature_sensor.read())
        except Exception as e:
            logger.debug("History: skip air_temp: %s", e)

        try:
            from app.sensors.pcb_temp.pcb_temp import get_pcb_temperature
            pcb_temp = float(get_pcb_temperature())
        except Exception as e:
            logger.debug("History: skip pcb_temp: %s", e)

        try:
            from app.sensors.light.routes import light_control
            light_percentage = float(light_control.get_brightness())
        except Exception as e:
            logger.debug("History: skip light_percentage: %s", e)

        try:
            row = SensorReading(
                water_level=water_level,
                humidity=humidity,
                air_temp=air_temp,
                pcb_temp=pcb_temp,
                light_percentage=light_percentage,
            )
            db.session.add(row)
            db.session.commit()
        except Exception as e:
            logger.warning("History: failed to save sensor snapshot: %s", e)
            db.session.rollback()


def log_pump_event(app: "Flask", is_on: bool, trigger: str, rule_id: str | None = None) -> None:
    """
    Append one row to pump_events. trigger must be "manual" or "rule".
    """
    if trigger not in ("manual", "rule"):
        trigger = "manual"
    with app.app_context():
        from app.models import PumpEvent, db
        try:
            db.session.add(PumpEvent(is_on=is_on, trigger=trigger, rule_id=rule_id if trigger == "rule" else None))
            db.session.commit()
        except Exception as e:
            logger.warning("History: failed to log pump event: %s", e)
            db.session.rollback()
