# Authentication and session baseline

HL-034 adds the deliberately small account layer needed before Helvetic Lens is exposed publicly. It does not depend on an external identity provider.

## Browser flow

- Registration accepts an email address, password, person name, and optional organization name. Email domains are IDNA-normalized and the complete address is Unicode-normalized and case-folded before uniqueness checks.
- A new registration always creates a new organization. Reusing a visible organization name never joins that organization. An empty organization name creates a personal workspace.
- Passwords are hashed with Argon2id. The browser receives a random session cookie and a separate CSRF cookie; only hashes of both tokens are persisted.
- The session cookie is `HttpOnly` and `SameSite=Lax`. Internet-facing production requires `Secure`; the readable CSRF cookie must match the `X-CSRF-Token` header on mutations.
- Logout revokes the server-side session immediately. Expired and revoked sessions cannot select an organization or access its records.

## Deployment modes

The current local demo remains available only with:

```text
APP_ENVIRONMENT=development
ALLOW_ANONYMOUS_DEV=true
SESSION_COOKIE_SECURE=false
```

An internet-facing deployment must use:

```text
APP_ENVIRONMENT=production
ALLOW_ANONYMOUS_DEV=false
SESSION_COOKIE_SECURE=true
```

Configuration validation refuses to start production with anonymous mutation or insecure cookies enabled. TLS termination is added in HL-048.

## Abuse and audit boundary

Redis counters limit registration, login, fetch, scan, invitation, and AI submission paths. Development and tests may fall back to process-local counters if Redis is absent; production fails closed instead. Security events retain only the event type, normalized account reference where useful, organization/user IDs, result, timestamp, and bounded network metadata. Passwords, raw session/CSRF tokens, cookies, and provider credentials are excluded from security events and integration logs.

This baseline intentionally defers email verification, password recovery, 2FA, and SSO to HL-054. Organization invitations and enforced administrator/viewer permissions are HL-035.
