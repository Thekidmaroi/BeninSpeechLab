# BeninSpeechLab v0.6 — Local admin setup and security boundary

**Status:** research pilot, NOT security-certified or approved for public deployment.

## Local setup (Windows PowerShell)

Set a long, unique admin password and a cryptographically random session secret.
Do not commit secrets or store them in the repository.

```powershell
$env:BENINSPEECH_ADMIN_PASSWORD = Read-Host "Mot de passe admin"
$env:BENINSPEECH_SESSION_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
uvicorn beninspeechlab.api:app --host 127.0.0.1 --port 8000
```

- Contributor page: http://127.0.0.1:8000/contribute
- Admin login: http://127.0.0.1:8000/admin/login
- Admin dashboard: http://127.0.0.1:8000/admin
- Legacy /studio redirects to /admin.

The admin login is disabled if the environment variables are not set.
Keep the same session secret across restarts to preserve active sessions.
Rotating it invalidates all existing cookies. Never reuse the example test credentials.

## Protections implemented

- Signed, HttpOnly, SameSite=Strict, eight-hour admin cookies (Secure flag on HTTPS).
- Explicit authorization on all private metadata, audio, review, statistics and ZIP endpoints.
- CSRF token on review and logout; Origin/Sec-Fetch-Site checks on mutations.
- Login attempt throttling (5 failures / 15 minutes per client, in process).
- HTTPS required when accessed from non-loopback hostnames.
- No-store, no-sniff, anti-framing and restrictive baseline CSP response headers.
- No database deletion or audio migration; existing private WAV and SQLite records are retained.

## Before any public deployment (BLOCKERS)

1. Commission a threat model, independent security review and penetration test.
2. Use a trusted authentication provider with individual accounts, MFA, recovery, revocation and audit logs. Current single-admin environment password and stateless cookies are only for a local pilot.
3. Put the app behind a properly configured TLS reverse proxy and validate trusted proxy headers. Current HTTPS detection is not proxy-aware.
4. Add persistent, distributed rate limits, upload quotas and abuse prevention to the **public** contribution endpoint, and protect against storage exhaustion.
5. Define legal basis, informed consent, withdrawal/deletion procedures, retention, backups, encryption at rest, incident response and applicable data-protection compliance.
6. Replace inline JavaScript/CSS with nonce/hash-based CSP and add dependency scanning, secret management, secure hosting and monitoring.
7. Audit dataset-release consent; approval of transcription alone does not authorize public sharing.
8. Add authorization tests for every new route, including multi-user and hostile network scenarios.

**Never** expose this pilot to the Internet merely by changing Uvicorn's bind address.
