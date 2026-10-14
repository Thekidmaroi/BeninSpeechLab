# v0.7 security roadmap — RBAC foundation

This branch implements **authorization groundwork**, not Keycloak integration yet.

## Current access model

- Existing password login issues a signed `super_admin` session only.
- Server-side role permissions are enforced for every private API.
- `super_admin`: statistics, audio, annotations, approval and exports.
- `manager`: statistics, audio, annotations and approval; **no exports**.
- `annotator`: audio and annotations; **no approval, statistics or exports**.
- No public endpoint permits users to assign or change their role.
- Tests create synthetic signed sessions to validate authorization; these are **not** a user provisioning mechanism.
- UI is still the original single admin dashboard; roles require separate UI before real user onboarding.

## Next step: vetted OIDC provider

Do not build a custom multi-user password database. Integrate Keycloak through
Authorization Code + PKCE, with exact redirect URI allowlists, validated ID tokens
(issuer, audience, signature, expiry, nonce), state validation and server-side
session storage. Require WebAuthn/passkeys or phishing-resistant MFA in the IdP.

Map Keycloak groups to app roles on the server using an explicit allowlist.
Never trust a browser-supplied role. Ensure disabling an IdP account revokes
application sessions. Preserve a safe migration path: test OIDC with local
accounts, then disable the shared-password login; do not run both auth methods
on the public deployment.

## Security limitations

Existing sessions are stateless and cannot be revoked individually before
expiry (except rotating the secret). Role changes are not immediately reflected
in existing cookies. Rate limits are in-memory, not distributed. The app has
no production audit log or persistent multi-user account management.
Do not deploy publicly until these limitations and the blockers in SECURITY.md
are resolved.
