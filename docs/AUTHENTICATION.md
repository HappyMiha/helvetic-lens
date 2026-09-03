# Authentication and session baseline

HL-034 adds the deliberately small account layer needed before Helvetic Lens is exposed publicly. It does not depend on an external identity provider.

## Browser flow

- Registration accepts an email address, password, person name, and optional organization name. Email domains are IDNA-normalized and the complete address is Unicode-normalized and case-folded before uniqueness checks. A 24-hour verification link is issued without delaying registration.
- A new registration always creates a new organization. Reusing a visible organization name never joins that organization. An empty organization name creates a personal workspace.
- Passwords are hashed with Argon2id. The browser receives a random session cookie and a separate CSRF cookie; only hashes of both tokens are persisted.
- The session cookie is `HttpOnly` and `SameSite=Lax`. Internet-facing production requires `Secure`; the readable CSRF cookie must match the `X-CSRF-Token` header on mutations.
- Logout revokes the server-side session immediately. Expired and revoked sessions cannot select an organization or access its records.
- **Forgot password?** always returns the same result for known and unknown addresses. Its 30-minute link works once; using it changes the Argon2id hash and revokes every existing session for that account.

## Deployment modes

The current local demo remains available only with:

```text
APP_ENVIRONMENT=development
ALLOW_ANONYMOUS_DEV=true
SESSION_COOKIE_SECURE=false
AUTH_EMAIL_MODE=development
```

An internet-facing deployment must use:

```text
APP_ENVIRONMENT=production
ALLOW_ANONYMOUS_DEV=false
SESSION_COOKIE_SECURE=true
PUBLIC_BASE_URL=https://lens.example.ch
AUTH_EMAIL_MODE=smtp
AUTH_EMAIL_FROM=Helvetic Lens <no-reply@example.ch>
AUTH_SMTP_HOST=smtp.example.ch
```

Configuration validation refuses to start production with anonymous mutation, insecure cookies, or the development mailbox enabled. TLS termination is added in HL-048.

## Abuse and audit boundary

Redis counters limit registration, login, fetch, scan, invitation, and AI submission paths. Development and tests may fall back to process-local counters if Redis is absent; production fails closed instead. Security events retain only the event type, normalized account reference where useful, organization/user IDs, result, timestamp, and bounded network metadata. Passwords, raw session/CSRF tokens, cookies, and provider credentials are excluded from security events and integration logs.

## Verification and recovery data

The database stores only a SHA-256 hash of each one-time token, its purpose, user, expiry, and consumed/revoked timestamps. Raw tokens are never written to security events or integration logs. Request responses are deliberately identical whether an account exists, and the request and completion routes have separate rate limits.

`AUTH_EMAIL_MODE=development` writes message files under the private `auth-mailbox` directory in the application data volume. These files contain live links, are deleted after 48 hours, and must never be copied into Git or exposed by a web server. Production rejects this mode. Configure SMTP for a shared deployment; after changing email delivery settings, restart API and worker containers.

If SMTP is unavailable, registration still succeeds and the user can request another verification message later. Password-reset requests also keep their generic response so delivery failures cannot disclose whether an account exists. Operators should inspect server health and SMTP logs, correct delivery, and let the user request a new link; they should never extract or manually distribute token hashes from the database.

Changing a password signs out all browsers. Email verification does not change organization membership, invitations, roles, last-admin protection, or platform-admin status. TOTP and SSO remain deferred until a measured need justifies an established external provider or standard library.

## Organization roles and invitations

HL-035 adds two organization roles. An `organization_admin` manages documents, scans, AI submissions, prompts, provider settings, the company profile, invitations, and members. A `viewer` can inspect the organization's full saved workspace and AI history, while matching write controls are absent and direct mutation requests return `403`.

Invitation tokens are random, stored only as hashes, bound to a normalized email address, valid for seven days, and accepted once. Creating a replacement invitation revokes any older pending invitation for that organization and email. Removing a member revokes their sessions for that organization. The last organization administrator cannot be removed or demoted; the Organization page provides an explicit handover.

The deployment-wide `platform_admin` flag is independent of organization membership. Manage it from inside the API container:

```sh
helvetic-lens-admin list
helvetic-lens-admin promote owner@example.ch
helvetic-lens-admin demote owner@example.ch
```

Commands are idempotent and audited, promotion requires an existing local account, and demotion refuses to remove the last platform administrator. Platform status does not bypass organization membership filters.
