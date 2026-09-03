# Account recovery runbook

Helvetic Lens keeps recovery deliberately small: verified email and a one-time password-reset link. Organization roles, invitations, and platform administration remain independent.

## Normal user flow

1. A registered user can resend verification from **Organization**. The verification link expires after 24 hours and works once.
2. **Forgot password?** on the sign-in page accepts an email and always displays the same response. A valid reset link expires after 30 minutes and works once.
3. Completing a reset changes the password and revokes all existing sessions. The user signs in again with the new password.

Requesting another link revokes any older unused link of the same type. Tenants cannot use these routes to join an organization, elevate a role, or bypass an invitation.

## Operator checks

- Confirm `PUBLIC_BASE_URL` is the externally reachable HTTPS address.
- Confirm `AUTH_EMAIL_MODE=smtp`, `AUTH_EMAIL_FROM`, and `AUTH_SMTP_HOST` before public use. Add SMTP credentials only through deployment secrets or the untracked `.env` file.
- Never use the development mailbox in production. Locally, inspect the private application data volume only when testing delivery and delete any copied message after use.
- If delivery fails, repair SMTP and ask the user to request a new link. Do not disclose whether an email is registered and do not retrieve token hashes from PostgreSQL.
- If account ownership cannot be established through email, do not change its password in the database. Platform administrators can be recovered through the documented CLI, but that does not grant access to an organization.

## Retention and audit

Raw email links exist only in transit and, in development, in short-lived mailbox files removed after 48 hours. PostgreSQL retains token hashes and lifecycle timestamps as security evidence; expired and consumed hashes cannot authenticate. Minimal security events record request/completion outcomes without passwords, cookies, raw tokens, or message bodies. Backups must receive the same protection and retention policy as the main account database.
