# Local Keycloak OIDC pilot

This is a **local test integration**, not production-ready SSO.

Keycloak realm: `beninspeechlab`; client: `beninspeechlab-web` (confidential, Standard Flow ON, PKCE S256).
Exact redirect: `http://127.0.0.1:8000/auth/callback`.

Set environment variables **in the PowerShell session running uvicorn**, never in Git:

```powershell
$env:BENINSPEECH_OIDC_ISSUER="http://127.0.0.1:8080/realms/beninspeechlab"
$env:BENINSPEECH_OIDC_CLIENT_ID="beninspeechlab-web"
$env:BENINSPEECH_OIDC_REDIRECT_URI="http://127.0.0.1:8000/auth/callback"
$env:BENINSPEECH_OIDC_CLIENT_SECRET=Read-Host "Keycloak client secret"
# Reuse your existing BENINSPEECH_SESSION_SECRET (at least 32 characters).
python -m pip install -e ".[dev]"
python -m pytest -q
python -m uvicorn beninspeechlab.api:app --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/admin/login` and click **Se connecter avec Keycloak**.
Authenticate as `bsl-admin` (realm role `super_admin`). Never paste secrets into chat.
Use the same hostname (127.0.0.1) for both services.

**Limitations:** OIDC pending states are in process memory, so a single worker is required.
App sessions remain stateless for up to eight hours; disabling a Keycloak account does
not immediately revoke an existing app session. Logout clears the app cookie only, not
the Keycloak SSO session. Existing shared-password login remains enabled for migration.
Before public deployment: persistent revocable sessions, Keycloak end-session integration,
MFA, HTTPS, audit logging, and removal of shared-password fallback are required.
