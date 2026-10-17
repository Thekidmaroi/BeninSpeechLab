"""Read-only Keycloak user directory for the local administration pilot.

Uses a dedicated confidential service-account client with realm-management
view-users permission. Never expose its client secret to the browser.
"""
import os
import httpx
from fastapi import HTTPException


def list_users():
    issuer = os.environ.get("BENINSPEECH_OIDC_ISSUER", "").rstrip("/")
    client_id = os.environ.get("BENINSPEECH_KC_ADMIN_CLIENT_ID", "")
    client_secret = os.environ.get("BENINSPEECH_KC_ADMIN_CLIENT_SECRET", "")
    if not issuer or not client_id or not client_secret:
        raise HTTPException(503, "Keycloak user directory not configured")
    if not (issuer.startswith("https://") or issuer.startswith("http://127.0.0.1:8080/") or issuer.startswith("http://localhost:8080/")):
        raise HTTPException(503, "Keycloak HTTPS required outside local development")
    realm = issuer.rsplit("/", 1)[-1]
    base = issuer.split("/realms/", 1)[0]
    if "/realms/" not in issuer or not realm:
        raise HTTPException(503, "Invalid Keycloak issuer")
    try:
        with httpx.Client(timeout=8) as client:
            token_response = client.post(
                issuer + "/protocol/openid-connect/token",
                data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            )
            token_response.raise_for_status()
            token = token_response.json()["access_token"]
            headers = {"Authorization": "Bearer " + token}
            response = client.get(base + "/admin/realms/" + realm + "/users",
                                  params={"max": 100}, headers=headers)
            response.raise_for_status()
            users = response.json()
            result = []
            for user in users:
                user_id = user["id"]
                roles_response = client.get(
                    base + "/admin/realms/" + realm + "/users/" + user_id + "/role-mappings/realm",
                    headers=headers,
                )
                roles_response.raise_for_status()
                roles = sorted(
                    role["name"] for role in roles_response.json()
                    if role.get("name") in {"super_admin", "manager", "annotator"}
                )
                result.append({
                    "id": user_id,
                    "username": user.get("username", ""),
                    "enabled": bool(user.get("enabled")),
                    "roles": roles,
                })
            return result
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, "Unable to retrieve Keycloak users") from exc
