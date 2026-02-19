"""
SQLite models for passkey auth: User and WebAuthnCredential.
"""
from __future__ import annotations

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)  # username or email
    display_name: Mapped[str] = mapped_column(nullable=False, default="")
    email: Mapped[str | None] = mapped_column(nullable=True, unique=True)  # for allowed-users check

    credentials: Mapped[list["WebAuthnCredential"]] = relationship(
        "WebAuthnCredential", back_populates="user", cascade="all, delete-orphan"
    )

    def to_webauthn_user(self):
        """Return (user_id_bytes, user_name, user_display_name) for webauthn options."""
        return (self.id.to_bytes(8, "big"), self.name, self.display_name or self.name)


class WebAuthnCredential(db.Model):
    __tablename__ = "webauthn_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    credential_id: Mapped[bytes] = mapped_column(db.LargeBinary, nullable=False, unique=True)
    public_key: Mapped[bytes] = mapped_column(db.LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(nullable=False, default=0)

    user: Mapped["User"] = relationship("User", back_populates="credentials")


# Singleton row (id=1) for gauge/alert thresholds and alert toggles
class AppSettings(db.Model):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)  # always 1
    water_level_min: Mapped[float] = mapped_column(nullable=False, default=13.0)
    water_level_max: Mapped[float] = mapped_column(nullable=False, default=8.5)
    water_alert_threshold: Mapped[float] = mapped_column(nullable=False, default=12.0)
    air_temp_min: Mapped[float] = mapped_column(nullable=False, default=32.0)
    air_temp_max: Mapped[float] = mapped_column(nullable=False, default=100.0)
    air_temp_high_alert_threshold: Mapped[float] = mapped_column(nullable=False, default=80.0)
    air_temp_low_alert_threshold: Mapped[float] = mapped_column(nullable=False, default=65.0)
    humidity_min: Mapped[float] = mapped_column(nullable=False, default=0.0)
    humidity_max: Mapped[float] = mapped_column(nullable=False, default=100.0)
    humidity_low_alert_threshold: Mapped[float] = mapped_column(nullable=False, default=40.0)
    humidity_high_alert_threshold: Mapped[float] = mapped_column(nullable=False, default=90.0)
    pcb_temp_min: Mapped[float] = mapped_column(nullable=False, default=75.0)
    pcb_temp_max: Mapped[float] = mapped_column(nullable=False, default=130.0)
    pcb_temp_alert_threshold: Mapped[float] = mapped_column(nullable=False, default=110.0)
    water_level_alerts_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    humidity_alerts_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    air_temp_alerts_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    pcb_temp_alerts_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    # Slack notifications (webhook from settings overrides SLACK_WEBHOOK_URL env)
    slack_webhook_url: Mapped[str | None] = mapped_column(nullable=True, default=None)
    slack_cooldown_minutes: Mapped[int] = mapped_column(nullable=False, default=15)
    slack_notifications_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    slack_runtime_errors_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    plant_of_the_day_slack_time: Mapped[str] = mapped_column(nullable=False, default="09:35")

    def to_dict(self):
        return {
            "water_level_min": self.water_level_min,
            "water_level_max": self.water_level_max,
            "water_alert_threshold": self.water_alert_threshold,
            "air_temp_min": self.air_temp_min,
            "air_temp_max": self.air_temp_max,
            "air_temp_high_alert_threshold": self.air_temp_high_alert_threshold,
            "air_temp_low_alert_threshold": self.air_temp_low_alert_threshold,
            "humidity_min": self.humidity_min,
            "humidity_max": self.humidity_max,
            "humidity_low_alert_threshold": self.humidity_low_alert_threshold,
            "humidity_high_alert_threshold": self.humidity_high_alert_threshold,
            "pcb_temp_min": self.pcb_temp_min,
            "pcb_temp_max": self.pcb_temp_max,
            "pcb_temp_alert_threshold": self.pcb_temp_alert_threshold,
            "water_level_alerts_enabled": self.water_level_alerts_enabled,
            "humidity_alerts_enabled": self.humidity_alerts_enabled,
            "air_temp_alerts_enabled": self.air_temp_alerts_enabled,
            "pcb_temp_alerts_enabled": self.pcb_temp_alerts_enabled,
            "slack_webhook_url": self.slack_webhook_url,
            "slack_cooldown_minutes": self.slack_cooldown_minutes,
            "slack_notifications_enabled": self.slack_notifications_enabled,
            "slack_runtime_errors_enabled": self.slack_runtime_errors_enabled,
            "plant_of_the_day_slack_time": self.plant_of_the_day_slack_time,
        }


# Historical sensor readings (polled every 5 minutes)
class SensorReading(db.Model):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    water_level: Mapped[float | None] = mapped_column(nullable=True)  # cm
    humidity: Mapped[float | None] = mapped_column(nullable=True)  # %
    air_temp: Mapped[float | None] = mapped_column(nullable=True)  # F
    pcb_temp: Mapped[float | None] = mapped_column(nullable=True)  # F
    light_percentage: Mapped[float | None] = mapped_column(nullable=True)  # 0-100


# Pump on/off events (manual or rule)
class PumpEvent(db.Model):
    __tablename__ = "pump_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    is_on: Mapped[bool] = mapped_column(nullable=False)  # True = turned on, False = turned off
    trigger: Mapped[str] = mapped_column(nullable=False)  # "manual" or "rule"
    rule_id: Mapped[str | None] = mapped_column(nullable=True)  # set when trigger is "rule"
