"""
Passkey (WebAuthn) registration and authentication.
"""
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
    base64url_to_bytes,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)
import jwt
from datetime import datetime, timedelta, timezone

from app.models import db, User, WebAuthnCredential

auth_blueprint = Blueprint("auth", __name__, url_prefix="/auth")

# User-facing message when registration is refused (email not in ALLOWED_EMAILS)
REGISTRATION_REFUSED_MESSAGE = "Sorry, we're not accepting new users at this time!"

# In-memory challenge storage (single process). Key: "registration" | "authentication"
_challenges: dict[str, bytes] = {}
# Store email for the in-progress registration (so register can find the user)
_registration_email: str | None = None
_log = logging.getLogger(__name__)


def _log_registration_refused(email: str) -> None:
    """Append a line to the registration-refused log file with request details."""
    try:
        log_dir = current_app.instance_path
        log_path = os.path.join(log_dir, "registration_refused.log")
        ts = datetime.now(timezone.utc).isoformat()
        remote = request.remote_addr or ""
        user_agent = (request.headers.get("User-Agent") or "").replace("\n", " ")
        path = request.path or ""
        method = request.method or ""
        line = f"{ts}\trefused_email={email}\tremote={remote}\tmethod={method}\tpath={path}\tuser_agent={user_agent}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        _log.warning("Could not write to registration_refused.log: %s", e)


def _get_allowed_emails():
    """List of allowed email addresses from config."""
    return list(current_app.config.get("ALLOWED_EMAILS") or [])


def _get_or_create_user_for_email(email: str):
    """Get or create a user for the given allowed email."""
    email = email.strip().lower()
    allowed = _get_allowed_emails()
    if not allowed:
        # No ALLOWED_EMAILS: fall back to single admin user (backward compat)
        user = User.query.filter_by(email=None).first() or User.query.first()
        if user is None:
            user = User(name="admin", display_name="Admin", email=None)
            db.session.add(user)
            db.session.commit()
            _log.info("Created default user 'admin' for passkey registration.")
        return user
    if email not in allowed:
        raise ValueError("Email not allowed to register")
    user = User.query.filter_by(email=email).first()
    if user is None:
        # Use email as name; display_name = part before @
        display = email.split("@")[0] if "@" in email else email
        user = User(name=email, display_name=display, email=email)
        db.session.add(user)
        db.session.commit()
        _log.info("Created user for allowed email: %s", email)
    return user


def _get_webauthn_rp_id_and_origin():
    """
    Return (rp_id, origin) for the current request. Uses ENVIRONMENT and/or
    request Origin to choose between LOCAL and PROD when both are configured.
    """
    env = current_app.config.get("ENVIRONMENT") or ""
    origin_header = (request.headers.get("Origin") or "").strip()
    rp_id_local = current_app.config.get("WEBAUTHN_RP_ID_LOCAL") or "localhost"
    origin_local = current_app.config.get("WEBAUTHN_ORIGIN_LOCAL") or "http://localhost:5173"
    rp_id_prod = (current_app.config.get("WEBAUTHN_RP_ID_PROD") or "").strip()
    origin_prod = (current_app.config.get("WEBAUTHN_ORIGIN_PROD") or "").strip()
    rp_id_fallback = current_app.config.get("WEBAUTHN_RP_ID") or "localhost"
    origin_fallback = current_app.config.get("WEBAUTHN_ORIGIN") or "http://localhost:5173"

    if env == "local":
        return (rp_id_local, origin_local)
    if env == "prod" and rp_id_prod and origin_prod:
        return (rp_id_prod, origin_prod)

    # ENVIRONMENT is "both" or unset: choose by request Origin so local and prod can work at once
    if origin_header == origin_local:
        return (rp_id_local, origin_local)
    if origin_prod and origin_header == origin_prod:
        return (rp_id_prod, origin_prod)

    return (rp_id_fallback, origin_fallback)


def _get_webauthn_config():
    rp_id, origin = _get_webauthn_rp_id_and_origin()
    return {"rp_id": rp_id, "origin": origin}


# ---- Registration ----

@auth_blueprint.route("/register/options", methods=["GET"])
def register_options():
    """Return PublicKeyCredentialCreationOptions for the client. Requires ?email= for allowed-users mode."""
    global _registration_email
    try:
        email = (request.args.get("email") or "").strip().lower()
        allowed = _get_allowed_emails()
        if allowed and not email:
            return jsonify({"error": "Email is required"}), 400
        if allowed and email not in allowed:
            _log_registration_refused(email)
            return jsonify({"error": REGISTRATION_REFUSED_MESSAGE}), 403
        user = _get_or_create_user_for_email(email) if email else _get_or_create_user_for_email("")
        user_id, user_name, user_display_name = user.to_webauthn_user()
        rp_id, _ = _get_webauthn_rp_id_and_origin()
        rp_name = current_app.config.get("WEBAUTHN_RP_NAME", "Garden of Eden")
        challenge = secrets.token_bytes(32)
        _challenges["registration"] = challenge
        _registration_email = email if allowed else None
        options = generate_registration_options(
            rp_id=rp_id,
            rp_name=rp_name,
            user_id=user_id,
            user_name=user_name,
            user_display_name=user_display_name,
            challenge=challenge,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        return jsonify(json.loads(options_to_json(options)))
    except ValueError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        _log.exception("register_options")
        return jsonify({"error": str(e)}), 500


@auth_blueprint.route("/register", methods=["POST"])
def register():
    """Verify registration response and store the credential. Body may include email for allowed-users mode."""
    global _registration_email
    try:
        challenge = _challenges.pop("registration", None)
        if not challenge:
            return jsonify({"error": "No registration in progress or expired"}), 400
        body = request.get_json() or {}
        credential = body.get("credential")
        if not credential:
            return jsonify({"error": "Missing credential"}), 400
        email = (body.get("email") or _registration_email or "").strip().lower()
        _registration_email = None
        allowed = _get_allowed_emails()
        if allowed and email not in allowed:
            _log_registration_refused(email)
            return jsonify({"error": REGISTRATION_REFUSED_MESSAGE}), 403
        user = _get_or_create_user_for_email(email) if email else _get_or_create_user_for_email("")
        rp_id, origin = _get_webauthn_rp_id_and_origin()
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_origin=origin,
            expected_rp_id=rp_id,
            require_user_verification=False,
        )
        cred = WebAuthnCredential(
            user_id=user.id,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
        )
        db.session.add(cred)
        db.session.commit()
        return jsonify({"ok": True, "message": "Passkey registered"})
    except Exception as e:
        _log.exception("register verify")
        return jsonify({"error": str(e)}), 400


# ---- Authentication ----

@auth_blueprint.route("/login/options", methods=["GET"])
def login_options():
    """Return PublicKeyCredentialRequestOptions."""
    try:
        creds = WebAuthnCredential.query.all()
        allow_credentials = None
        if creds:
            from webauthn.helpers.structs import PublicKeyCredentialDescriptor
            allow_credentials = [PublicKeyCredentialDescriptor(id=c.credential_id) for c in creds]
        rp_id, _ = _get_webauthn_rp_id_and_origin()
        challenge = secrets.token_bytes(32)
        _challenges["authentication"] = challenge
        options = generate_authentication_options(
            rp_id=rp_id,
            challenge=challenge,
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        return jsonify(json.loads(options_to_json(options)))
    except Exception as e:
        _log.exception("login_options")
        return jsonify({"error": str(e)}), 500


@auth_blueprint.route("/login", methods=["POST"])
def login():
    """Verify authentication response and return a JWT."""
    try:
        challenge = _challenges.pop("authentication", None)
        if not challenge:
            return jsonify({"error": "No login in progress or expired"}), 400
        body = request.get_json() or {}
        credential = body.get("credential")
        if not credential:
            return jsonify({"error": "Missing credential"}), 400
        raw_id = credential.get("rawId") or credential.get("id")
        if not raw_id:
            return jsonify({"error": "Missing credential id"}), 400
        cred_id = base64url_to_bytes(raw_id) if isinstance(raw_id, str) else raw_id
        cred = WebAuthnCredential.query.filter_by(credential_id=cred_id).first()
        if not cred:
            return jsonify({"error": "Unknown credential"}), 400
        rp_id, origin = _get_webauthn_rp_id_and_origin()
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_origin=origin,
            expected_rp_id=rp_id,
            credential_public_key=cred.public_key,
            credential_current_sign_count=cred.sign_count,
            require_user_verification=False,
        )
        cred.sign_count = verification.new_sign_count
        db.session.commit()
        user = cred.user
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"])
        payload = {
            "sub": str(user.id),
            "name": user.name,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(
            payload,
            current_app.config["SECRET_KEY"],
            algorithm=current_app.config["JWT_ALGORITHM"],
        )
        return jsonify({"token": token, "user": {"id": user.id, "name": user.name}})
    except Exception as e:
        _log.exception("login verify")
        return jsonify({"error": str(e)}), 400


@auth_blueprint.route("/me", methods=["GET"])
def me():
    """Return current user from JWT (optional; used by frontend to check session)."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization"}), 401
    token = auth[7:].strip()
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
        user_id = int(payload["sub"])
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 401
        return jsonify({"user": {"id": user.id, "name": user.name}})
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid or expired token"}), 401
