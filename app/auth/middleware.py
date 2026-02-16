"""
Require JWT for non-auth routes when AUTH_ENABLED is True.
"""
import logging
import jwt
from flask import request, g, jsonify

_log = logging.getLogger(__name__)


def require_auth(app):
    """Register before_request to enforce JWT on protected routes."""

    @app.before_request
    def _check_auth():
        if not app.config.get("AUTH_ENABLED", True):
            return None
        if request.method == "OPTIONS":
            return None  # Let CORS handle preflight; don't require auth
        if request.path.startswith("/auth/"):
            return None
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401
        token = auth[7:].strip()
        try:
            payload = jwt.decode(
                token,
                app.config["SECRET_KEY"],
                algorithms=[app.config["JWT_ALGORITHM"]],
            )
            g.current_user_id = int(payload["sub"])
            g.current_user_name = payload.get("name", "")
        except jwt.InvalidTokenError as e:
            _log.warning("JWT verification failed: %s", e)
            return jsonify({"error": "Invalid or expired token"}), 401
        return None
