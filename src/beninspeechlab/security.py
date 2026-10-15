"""Minimal single-admin session security for the local research pilot.

Deployment requires TLS, a stable random secret and a strong password.
For a multi-admin production service replace this with a vetted identity provider.
"""
import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

COOKIE = "bsl_admin"
SESSION_SECONDS = 8 * 3600
ROLES = {"super_admin", "manager", "annotator"}
PERMISSIONS = {
    "read_stats": {"super_admin", "manager"},
    "read_recordings": {"super_admin", "manager", "annotator"},
    "review_recordings": {"super_admin", "manager", "annotator"},
    "approve_recordings": {"super_admin", "manager"},
    "export_corpus": {"super_admin"},
}

_attempts = defaultdict(list)
_attempt_lock = threading.Lock()


def configured():
    return bool(os.environ.get("BENINSPEECH_ADMIN_PASSWORD")) and len(
        os.environ.get("BENINSPEECH_SESSION_SECRET", "")
    ) >= 32


def _secret():
    if len(os.environ.get("BENINSPEECH_SESSION_SECRET", "")) < 32:
        raise HTTPException(503, "Admin authentication is not configured")
    return os.environ["BENINSPEECH_SESSION_SECRET"].encode("utf-8")


def secure_transport(request: Request):
    # Do not trust forwarded headers unless a trusted proxy is explicitly configured.
    if request.url.scheme != "https" and request.url.hostname not in {"localhost", "127.0.0.1", "::1", "testserver"}:
        raise HTTPException(403, "HTTPS required")


def same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        expected = request.url
        if parsed.scheme != expected.scheme or parsed.netloc != expected.netloc:
            raise HTTPException(403, "Cross-origin request denied")
    elif request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site request denied")


def _signature(payload: str):
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def issue_session(role="super_admin"):
    if role not in ROLES:
        raise ValueError("Unknown role")
    payload = f"{int(time.time()) + SESSION_SECONDS}.{role}.{secrets.token_urlsafe(24)}"
    return payload + "." + _signature(payload)


def _session_payload(request: Request):
    token = request.cookies.get(COOKIE, "")
    try:
        expires, role, nonce, signature = token.split(".", 3)
        if role not in ROLES:
            return None
        payload = expires + "." + role + "." + nonce
        if int(expires) < time.time() or not hmac.compare_digest(signature, _signature(payload)):
            return None
        return payload
    except (ValueError, TypeError):
        return None


def require_admin(request: Request, *, mutation=False, permission=None):
    secure_transport(request)
    payload = _session_payload(request)
    if not payload:
        raise HTTPException(401, "Administrator login required")
    role = payload.split(".")[1]
    if permission and role not in PERMISSIONS.get(permission, set()):
        raise HTTPException(403, "Insufficient privileges")
    if mutation:
        same_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        expected = _signature("csrf:" + payload)
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(403, "CSRF token required")
    return payload


def csrf_token(request: Request):
    return _signature("csrf:" + require_admin(request))


def check_password(password: str, client_key: str):
    if not configured():
        raise HTTPException(503, "Admin authentication is not configured")
    now = time.monotonic()
    with _attempt_lock:
        recent = [t for t in _attempts[client_key] if now - t < 900]
        _attempts[client_key] = recent
        if len(recent) >= 5:
            raise HTTPException(429, "Too many attempts; retry later")
    expected = os.environ["BENINSPEECH_ADMIN_PASSWORD"]
    valid = hmac.compare_digest(
        hashlib.sha256(password.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )
    if not valid:
        with _attempt_lock:
            _attempts[client_key].append(now)
        raise HTTPException(401, "Invalid credentials")
    with _attempt_lock:
        _attempts.pop(client_key, None)


def current_role(request: Request):
    return require_admin(request).split(".")[1]
