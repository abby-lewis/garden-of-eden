import re
from pathlib import Path

from flask import Flask

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


def _ensure_sqlite_dir(uri: str) -> None:
    """If the database URI is SQLite, ensure the database file's parent directory exists."""
    if not uri or not uri.startswith("sqlite"):
        return
    # sqlite:///path or sqlite:////absolute/path
    match = re.match(r"sqlite:///(.+)$", uri)
    if not match:
        return
    path = Path(match.group(1))
    if not path.is_absolute():
        # Resolve relative to project root (parent of app/)
        root = Path(__file__).resolve().parent.parent
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)


def create_app(config_name):
    app = Flask(__name__)
    try:
        import config as project_config
        app.config["SECRET_KEY"] = project_config.SECRET_KEY
        app.config["AUTH_ENABLED"] = project_config.AUTH_ENABLED
        app.config["SQLALCHEMY_DATABASE_URI"] = project_config.SQLALCHEMY_DATABASE_URI
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["WEBAUTHN_RP_ID"] = project_config.WEBAUTHN_RP_ID
        app.config["WEBAUTHN_ORIGIN"] = project_config.WEBAUTHN_ORIGIN
        app.config["WEBAUTHN_RP_NAME"] = getattr(project_config, "WEBAUTHN_RP_NAME", "Garden of Eden")
        app.config["JWT_ALGORITHM"] = project_config.JWT_ALGORITHM
        app.config["JWT_EXPIRY_HOURS"] = project_config.JWT_EXPIRY_HOURS
        app.config["ALLOWED_EMAILS"] = getattr(project_config, "ALLOWED_EMAILS", [])
    except ImportError:
        app.config["SECRET_KEY"] = "dev-secret"
        app.config["AUTH_ENABLED"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/garden.db"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["WEBAUTHN_RP_ID"] = "localhost"
        app.config["WEBAUTHN_ORIGIN"] = "http://localhost:5173"
        app.config["WEBAUTHN_RP_NAME"] = "Garden of Eden"
        app.config["JWT_ALGORITHM"] = "HS256"
        app.config["JWT_EXPIRY_HOURS"] = 24
        app.config["ALLOWED_EMAILS"] = []

    db.init_app(app)
    with app.app_context():
        _ensure_sqlite_dir(app.config["SQLALCHEMY_DATABASE_URI"])
        db.create_all()

    require_auth(app)
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

    # @app.teardown_appcontext
    # def shutdown_session(exception=None):
        # pump_control = PumpControl()
        # pump_control.close()

    return app
