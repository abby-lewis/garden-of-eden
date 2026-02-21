import re
from pathlib import Path

from flask import Flask
from sqlalchemy import text

from app.models import db
from .auth.routes import auth_blueprint
from .auth.middleware import require_auth
from .sensors.light.routes import light_blueprint
from .sensors.pump.routes import pump_blueprint
from .sensors.distance.routes import distance_blueprint
from .sensors.temperature.routes import temperature_blueprint
from .sensors.humidity.routes import humidity_blueprint
from .sensors.pcb_temp.routes import pcb_temp_blueprint
from .sensors.camera.routes import camera_blueprint
from .schedules.routes import schedule_blueprint
from .settings.routes import settings_blueprint
from .plant_of_the_day.routes import plant_of_the_day_blueprint
from .history.routes import history_blueprint
from .backup.routes import backup_blueprint


def _migrate_app_settings_slack(app):
    """Add Slack-related columns to app_settings if missing (for existing DBs)."""
    from app.models import db
    with db.engine.connect() as conn:
        try:
            r = conn.execute(text("PRAGMA table_info(app_settings)"))
            cols = {row[1] for row in r}
        except Exception:
            return
        for col, spec in [
            ("slack_webhook_url", "TEXT"),
            ("slack_cooldown_minutes", "INTEGER NOT NULL DEFAULT 15"),
            ("slack_notifications_enabled", "INTEGER NOT NULL DEFAULT 1"),
            ("slack_runtime_errors_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("plant_of_the_day_slack_time", "TEXT NOT NULL DEFAULT '09:35'"),
        ]:
            if col not in cols:
                try:
                    conn.execute(text(f"ALTER TABLE app_settings ADD COLUMN {col} {spec}"))
                    conn.commit()
                except Exception:
                    conn.rollback()


def _register_error_handlers(app):
    """Send Slack notification on 500 if runtime errors enabled in settings."""
    @app.errorhandler(500)
    def handle_500(e):
        try:
            from app.alerts.slack import send_runtime_error
            send_runtime_error(app, e, "HTTP 500")
        except Exception:
            pass
        return {"error": "Internal Server Error"}, 500


def _normalize_sqlite_uri(uri: str) -> str:
    """
    For SQLite URIs, resolve the path to absolute (relative to project root) and ensure
    the database directory exists. Returns the URI to use (absolute path so CWD doesn't matter).
    """
    if not uri or not uri.startswith("sqlite"):
        return uri
    match = re.match(r"sqlite:///(.+)$", uri)
    if not match:
        return uri
    path = Path(match.group(1))
    if not path.is_absolute():
        root = Path(__file__).resolve().parent.parent
        path = (root / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use absolute path so SQLite doesn't depend on process CWD (e.g. when run via systemd)
    return f"sqlite:///{path}"


def create_app(config_name):
    app = Flask(__name__)
    try:
        import config as project_config
        app.config["SECRET_KEY"] = project_config.SECRET_KEY
        app.config["AUTH_ENABLED"] = project_config.AUTH_ENABLED
        app.config["ALLOW_NEW_USERS"] = getattr(project_config, "ALLOW_NEW_USERS", True)
        app.config["SQLALCHEMY_DATABASE_URI"] = project_config.SQLALCHEMY_DATABASE_URI
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["WEBAUTHN_RP_ID"] = project_config.WEBAUTHN_RP_ID
        app.config["WEBAUTHN_ORIGIN"] = project_config.WEBAUTHN_ORIGIN
        app.config["WEBAUTHN_RP_ID_LOCAL"] = getattr(project_config, "WEBAUTHN_RP_ID_LOCAL", "localhost")
        app.config["WEBAUTHN_ORIGIN_LOCAL"] = getattr(project_config, "WEBAUTHN_ORIGIN_LOCAL", "http://localhost:5173")
        app.config["WEBAUTHN_RP_ID_PROD"] = getattr(project_config, "WEBAUTHN_RP_ID_PROD", "")
        app.config["WEBAUTHN_ORIGIN_PROD"] = getattr(project_config, "WEBAUTHN_ORIGIN_PROD", "")
        app.config["ENVIRONMENT"] = getattr(project_config, "ENVIRONMENT", "")
        app.config["WEBAUTHN_RP_NAME"] = getattr(project_config, "WEBAUTHN_RP_NAME", "Garden of Eden")
        app.config["JWT_ALGORITHM"] = project_config.JWT_ALGORITHM
        app.config["JWT_EXPIRY_HOURS"] = project_config.JWT_EXPIRY_HOURS
        app.config["ALLOWED_EMAILS"] = getattr(project_config, "ALLOWED_EMAILS", [])
        app.config["PLANT_API_KEY"] = getattr(project_config, "PLANT_API_KEY", "")
        app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_sqlite_uri(app.config["SQLALCHEMY_DATABASE_URI"])
    except ImportError:
        app.config["SECRET_KEY"] = "dev-secret"
        app.config["AUTH_ENABLED"] = False
        app.config["ALLOW_NEW_USERS"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_sqlite_uri("sqlite:///instance/garden.db")
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["WEBAUTHN_RP_ID"] = "localhost"
        app.config["WEBAUTHN_ORIGIN"] = "http://localhost:5173"
        app.config["WEBAUTHN_RP_ID_LOCAL"] = "localhost"
        app.config["WEBAUTHN_ORIGIN_LOCAL"] = "http://localhost:5173"
        app.config["WEBAUTHN_RP_ID_PROD"] = ""
        app.config["WEBAUTHN_ORIGIN_PROD"] = ""
        app.config["ENVIRONMENT"] = ""
        app.config["WEBAUTHN_RP_NAME"] = "Garden of Eden"
        app.config["JWT_ALGORITHM"] = "HS256"
        app.config["JWT_EXPIRY_HOURS"] = 24
        app.config["ALLOWED_EMAILS"] = []
        app.config["PLANT_API_KEY"] = ""

    db.init_app(app)
    with app.app_context():
        db.create_all()
        _migrate_app_settings_slack(app)

    require_auth(app)
    _register_error_handlers(app)
    app.register_blueprint(auth_blueprint)
    # Register blueprints
    app.register_blueprint(light_blueprint, url_prefix='/light')
    app.register_blueprint(pump_blueprint, url_prefix='/pump')
    app.register_blueprint(distance_blueprint, url_prefix='/distance')
    app.register_blueprint(temperature_blueprint, url_prefix='/temperature')
    app.register_blueprint(humidity_blueprint, url_prefix='/humidity')
    app.register_blueprint(pcb_temp_blueprint, url_prefix='/pcb-temp')
    app.register_blueprint(camera_blueprint, url_prefix='/camera')
    app.register_blueprint(schedule_blueprint, url_prefix='/schedule/rules')
    app.register_blueprint(settings_blueprint, url_prefix='/settings')
    app.register_blueprint(plant_of_the_day_blueprint, url_prefix='/plant-of-the-day')
    app.register_blueprint(history_blueprint, url_prefix='/history')
    app.register_blueprint(backup_blueprint, url_prefix='/backup')

    # @app.teardown_appcontext
    # def shutdown_session(exception=None):
        # pump_control = PumpControl()
        # pump_control.close()

    return app
