"""Local-pilot Keycloak OIDC Authorization Code + PKCE S256 integration.

Pending login state is process-local. Use a shared server-side store before scaling.
"""
import base64
import hashlib
import os
import secrets
import threading
import time
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebToken, JsonWebKey
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from .security import COOKIE, SESSION_SECONDS, ROLES, issue_session, secure_transport

_pending = {}
_lock = threading.Lock()
_jwt = JsonWebToken(["RS256"])


def enabled():
    return all(os.environ.get(k) for k in (
        "BENINSPEECH_OIDC_ISSUER", "BENINSPEECH_OIDC_CLIENT_ID",
        "BENINSPEECH_OIDC_CLIENT_SECRET", "BENINSPEECH_OIDC_REDIRECT_URI",
        "BENINSPEECH_SESSION_SECRET",
    )) and len(os.environ["BENINSPEECH_SESSION_SECRET"]) >= 32


def config():
    if not enabled():
        raise HTTPException(503, "OIDC not configured")
    issuer = os.environ["BENINSPEECH_OIDC_ISSUER"].rstrip("/")
    if not issuer.startswith(("http://127.0.0.1:8080/", "http://localhost:8080/", "https://")):
        raise HTTPException(503, "OIDC issuer must use HTTPS outside local development")
    return issuer, os.environ["BENINSPEECH_OIDC_CLIENT_ID"], os.environ["BENINSPEECH_OIDC_CLIENT_SECRET"], os.environ["BENINSPEECH_OIDC_REDIRECT_URI"]


def discovery(issuer):
    try:
        with httpx.Client(timeout=8) as client:
            response = client.get(issuer + "/.well-known/openid-configuration")
            response.raise_for_status()
            data = response.json()
        if data.get("issuer") != issuer:
            raise ValueError("OIDC issuer mismatch")
        return data
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "OIDC provider unavailable or invalid") from exc


def begin(request: Request):
    secure_transport(request)
    issuer, client_id, _, redirect_uri = config()
    if str(request.base_url).rstrip("/") != redirect_uri.rsplit("/auth/callback", 1)[0]:
        raise HTTPException(400, "OIDC redirect origin mismatch")
    metadata = discovery(issuer)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
    with _lock:
        now = time.time()
        for key, item in list(_pending.items()):
            if item["expires"] < now:
                del _pending[key]
        _pending[state] = {"nonce": nonce, "verifier": verifier, "expires": now + 300}
    query = urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri,
        "scope": "openid profile email", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    return RedirectResponse(metadata["authorization_endpoint"] + "?" + query, status_code=302)


def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    secure_transport(request)
    issuer, client_id, client_secret, redirect_uri = config()
    if error or not code or not state:
        raise HTTPException(401, "OIDC login denied")
    with _lock:
        pending = _pending.pop(state, None)
    if not pending or pending["expires"] < time.time():
        raise HTTPException(401, "OIDC state invalid or expired")
    metadata = discovery(issuer)
    try:
        with httpx.Client(timeout=8) as client:
            response = client.post(metadata["token_endpoint"], data={
                "grant_type": "authorization_code", "code": code,
                "redirect_uri": redirect_uri, "client_id": client_id,
                "code_verifier": pending["verifier"],
            }, auth=(client_id, client_secret))
            response.raise_for_status()
            tokens = response.json()
            keys = client.get(metadata["jwks_uri"])
            keys.raise_for_status()
            jwks = JsonWebKey.import_key_set(keys.json())
        now = int(time.time())
        id_claims = _jwt.decode(tokens["id_token"], jwks, claims_options={
            "iss": {"essential": True, "value": issuer},
            "aud": {"essential": True, "value": client_id},
            "exp": {"essential": True},
            "iat": {"essential": True},
            "nonce": {"essential": True, "value": pending["nonce"]},
        })
        id_claims.validate(now=now, leeway=30)
        access_claims = _jwt.decode(tokens["access_token"], jwks, claims_options={
            "iss": {"essential": True, "value": issuer},
            "exp": {"essential": True},
        })
        access_claims.validate(now=now, leeway=30)
        if access_claims.get("azp") != client_id or id_claims.get("sub") != access_claims.get("sub"):
            raise ValueError("Token client or subject mismatch")
        roles = set(access_claims.get("realm_access", {}).get("roles", [])) & ROLES
        role = next((r for r in ("super_admin", "manager", "annotator") if r in roles), None)
        if not role:
            raise HTTPException(403, "No BeninSpeechLab role assigned")
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError, Exception) as exc:
        raise HTTPException(401, "OIDC token validation failed") from exc
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(COOKIE, issue_session(role), max_age=SESSION_SECONDS,
                        httponly=True, secure=request.url.scheme == "https",
                        samesite="lax", path="/")
    return response
