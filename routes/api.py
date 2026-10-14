"""
JSON API used by the Android app.

  Browser/WebView session (cookie)         -> /api/device/me, /api/device/link, /api/device/revoke
  Phone, in the background (Bearer token)  -> /api/transactions/raw

The background path cannot use the login cookie (the WebView may not even be running
when an SMS arrives), so a phone is "linked" once while the user is logged in: the
server issues a random token, the app stores it, and from then on uploads with
"Authorization: Bearer <token>".
"""
import hashlib
import secrets
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request, g
from flask_login import current_user

from models import db
from models.device_token import DeviceToken
from services.ingest import ingest_raw

api_bp = Blueprint("api", __name__, url_prefix="/api")

MAX_DEVICES_PER_USER = 10


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify(error="login_required"), 401
        return view(*args, **kwargs)
    return wrapper


def token_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="missing_token"), 401
        device = DeviceToken.query.filter_by(token_hash=_hash(header[7:].strip())).first()
        if device is None:
            return jsonify(error="invalid_token"), 401
        device.last_seen = datetime.utcnow()
        db.session.commit()
        g.device = device
        g.api_user = device.user
        return view(*args, **kwargs)
    return wrapper


@api_bp.route("/ping")
def ping():
    return jsonify(ok=True, app="Personal Expense Tracker")


@api_bp.route("/device/me")
@session_required
def device_me():
    return jsonify(user_id=current_user.id, name=current_user.name)


@api_bp.route("/device/link", methods=["POST"])
@session_required
def device_link():
    body = request.get_json(silent=True) or {}
    name = str(body.get("device_name") or "Android app")[:80]

    # keep the table tidy: drop the oldest tokens beyond the limit
    tokens = (DeviceToken.query.filter_by(user_id=current_user.id)
              .order_by(DeviceToken.created_at.asc()).all())
    for old in tokens[:max(0, len(tokens) - MAX_DEVICES_PER_USER + 1)]:
        db.session.delete(old)

    raw = secrets.token_urlsafe(32)
    db.session.add(DeviceToken(user_id=current_user.id, token_hash=_hash(raw), device_name=name))
    db.session.commit()
    return jsonify(token=raw, user_id=current_user.id, name=current_user.name), 201


@api_bp.route("/device/revoke", methods=["POST"])
@session_required
def device_revoke():
    removed = DeviceToken.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify(revoked=removed)


@api_bp.route("/transactions/raw", methods=["POST"])
@token_required
def transactions_raw():
    body = request.get_json(silent=True) or {}
    raw_text = body.get("raw_text")
    if not isinstance(raw_text, str) or not raw_text.strip() or len(raw_text) > 2000:
        return jsonify(error="raw_text must be a non-empty string (max 2000 chars)"), 400

    source = body.get("source") if body.get("source") in ("sms", "notification") else "sms"
    received_at = body.get("received_at")
    if not isinstance(received_at, (int, float)) or received_at <= 0:
        received_at = None

    result = ingest_raw(
        g.api_user, raw_text,
        source=source,
        sender=body.get("sender") if isinstance(body.get("sender"), str) else None,
        package=body.get("package") if isinstance(body.get("package"), str) else None,
        received_at_ms=received_at,
    )
    return jsonify(result), (201 if result["status"] == "created" else 200)
