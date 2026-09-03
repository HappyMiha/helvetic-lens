# Platform and organization administration

Helvetic Lens separates installation-wide controls from organization data. `/admin` is available only to a platform administrator when authentication is enabled. It summarizes service health, connector freshness, durable queues, failed jobs, model slots, GPU/RAM/disk signals, backup presence, retention rules, and recent administrative outcomes. It links to the bounded model, connector, job, log, and global-prompt controls; the browser never receives a Docker socket or arbitrary command runner.

`/organization` is scoped to the active organization. It combines members and invitations with direct links to its watchlist/custom sources, company profile, prompt override, AI provider opt-in, usage, and quotas. Viewers can inspect shared evidence but cannot mutate it. Organization administrators cannot open any `/api/admin/*` endpoint, including reads.

## Credentials

Saved cloud-provider credentials are write-only. They are encrypted with AES-256-GCM before entering PostgreSQL, omitted from API responses and integration logs, and are exposed only as configured/replacement/removal/test status. Set `HELVETIC_LENS_CREDENTIAL_KEY` to a long random deployment secret and back it up separately from the database. Local development creates `.credential-key` in the shared document-data volume; losing that file makes saved provider credentials intentionally unrecoverable. Existing plaintext records are encrypted during the first startup after this upgrade.

Enabling a cloud provider remains an explicit organization action. The settings page labels local versus cloud execution and requires a confirmation before sending a test request to a newly selected cloud destination.

## Audit and recovery

Every non-authentication API mutation records the actor, organization, scope, method/path, time, response status, and success/failure result without recording the request body. Destructive actions keep their existing UI confirmation. Diagnostics are bounded and secrets are redacted before storage.

The web console is not the bootstrap dependency for platform access. From the API environment, use:

```text
helvetic-lens-admin list
helvetic-lens-admin grant administrator@example.ch
helvetic-lens-admin revoke administrator@example.ch
```

The CLI refuses to remove the last platform administrator. Backup status is observational: place database/artifact backup markers in the configured data volume's `backups` directory or connect the deployment's backup job there. A missing backup is shown as `Not configured`, never as healthy.
