# Monitoring v2 deployment on HappyDucky02

This runbook implements MV2-072. The Monitoring application follows
`codex/HappyDucky02/monitoring-v2` and serves `https://monitoring.helveticlens.ch`.
The main product and hackathon channel remains `main` on HappySnowman at
`https://helveticlens.ch`. Keep the frozen `v1.0.0-hackathon-mvp` tag unchanged.
An installed environment does not complete Pollen Watch or establish high availability.

## Persistent instance layout

Use `C:\Users\HappyDucky02\Documents\Codex\helvetic-lens-monitoring` as the durable
instance root, outside development worktrees. The example configuration is
[monitoring-instance.example.json](../deploy/monitoring-instance.example.json).
Copy it to `<root>\monitoring-instance.json` and review the absolute paths.
This file contains routing and resource configuration, never credentials.

| Path | Purpose |
| --- | --- |
| `source` | Dedicated clone of the trusted repository; fetched branch supplies immutable candidates |
| `releases` | Immutable application releases |
| `controller` | Explicitly pinned release manager, launcher, controller revision and deployment lock |
| `state` | Deployment status, history and logs |
| `private\monitoring.env` | Separate application, database, queue and SMTP credentials |
| `private\cloudflared` | Dedicated remotely managed tunnel token file |
| `backups` | Separate backup directory, selected by `HELVETIC_LENS_BACKUP_DIR` in the private env file |

Keep these paths independent of the MVP instance. The Compose project is
`helvetic-lens-v2` and the Docker context is `desktop-linux`. Do not reuse existing
database/queue passwords, volumes, application state, model data or tunnel routes.
Persist `HELVETIC_LENS_BACKUP_DIR` as the dedicated absolute backup path; it is an
application environment setting, not an extra instance JSON key. Use forward slashes
in JSON and Docker bind-path values. Shared numeric feature logic does not imply
shared deployment resources.

## Before installation

1. Review and publish the controller commit on the dedicated Monitoring branch.
   Clone/fetch the trusted repository into `source`. The installer checks the exact
   commit against the fetched `origin/codex/HappyDucky02/monitoring-v2`; it never
   fetches or trusts a moving branch as the controller revision.
2. Select an existing native Windows Python 3.11+ executable by absolute path.
   Keep that interpreter installed for the life of the scheduled task. Do not use
   a temporary environment, shell alias or Microsoft Store execution stub.
3. Start Docker Desktop with its Linux engine and verify the explicit context:
   `docker --context desktop-linux info`. Do not restart the global daemon or
   change WSL integration to repair a different instance.
4. Prepare the private environment with separate credentials, valid SMTP and the
   production configuration requirements. Create the dedicated tunnel route for
   `monitoring.helveticlens.ch` to `http://web:3000`. Keep normal authentication enabled.
   Place its token in `private\cloudflared\token`, outside Git. The Monitoring Compose
   overlay mounts it and uses `--token-file /etc/cloudflared/token`; never put the
   secret itself in command arguments, a Compose environment value or logs. Do not
   alter the main product's tunnel. Token-file support requires cloudflared 2025.4.0
   or newer. See [Cloudflare tunnel parameters](https://developers.cloudflare.com/tunnel/advanced/run-parameters/).
5. Protect the `private` directory, its existing contents and `backups` using Windows
   ACLs scoped to this instance. Permit the current deployment user and SYSTEM;
   remove inherited broad access as appropriate. Inspect the resulting ACLs with
   `Get-Acl`. Python `chmod` is not a Windows confidentiality control. The installer
   protects its controller directory and JSON file, but does not manage secret files.
6. Inspect the resource values in the Monitoring Compose overlay and confirm the
   host has room for a clean install and one candidate build/test. The JSON QA
   defaults bound each quality container to 2 CPUs and 4 GiB; the API test timeout
   is 7,200 seconds. Account for application/model resources separately. Initial
   model downloads need time and free disk space; do not borrow the MVP model volume.

## Install the pinned controller and scheduler

Run as the Windows user who owns this instance and runs Docker Desktop. The
installer uses a limited interactive principal; administrator elevation and a
service password are not part of this workflow.

```powershell
$config = 'C:\Users\HappyDucky02\Documents\Codex\helvetic-lens-monitoring\monitoring-instance.json'
$python = '<absolute path to your installed python.exe>'
$revision = '<reviewed full lowercase 40-character commit SHA>'

& .\deploy\install-monitoring-auto-deploy.ps1 -ConfigPath $config -PythonExecutable $python -ControllerCommit $revision -ValidateOnly
& .\deploy\install-monitoring-auto-deploy.ps1 -ConfigPath $config -PythonExecutable $python -ControllerCommit $revision -StartDisabled
```

If Windows PowerShell's default execution policy blocks local scripts, launch this
reviewed installer with `powershell.exe -NoProfile -ExecutionPolicy RemoteSigned
-File .\deploy\install-monitoring-auto-deploy.ps1` followed by the same parameters.
The scheduled launcher also uses `RemoteSigned` for its own process. No user or
machine execution policy is changed; enforced Group Policy still applies. Do not
remove file trust labels or change system policy to work around an enforced policy.

`-ValidateOnly` checks paths, configuration, interpreter and Git provenance without
creating files, changing scheduled tasks or contacting the network. Installation
preserves the configuration file bytes. It extracts the manager from the exact Git
object, compiles it, and records the revision and SHA-256 in `controller\controller.json`.
Reinstallation with the same inputs keeps one task; an existing task with a different
owner or command is rejected. Replacing a different manager preserves its previous
bytes as a uniquely named backup inside `controller`.

`-StartDisabled` registers the task in a paused state before any trigger can run.
Use it while credentials or first bootstrap are pending. Reinstallation preserves an
existing paused task even if that switch is omitted; resuming it is an explicit
`Enable-ScheduledTask` action after successful bootstrap. Without the switch a new
task is enabled.

The one task is `HelveticLens-Monitoring-v2-AutoDeploy`. Its hidden PowerShell launcher
persists the exact Python executable, manager and `--config` path. It sets
`GIT_TERMINAL_PROMPT=0` for every invocation, triggers at logon and every two minutes,
and uses `IgnoreNew` to prevent scheduler overlap. The controller and installer share
the deployment lock. No user-wide environment setting is needed.

## First deployment and verification

The scheduler does not silently turn an empty instance into production. Bootstrap
the first release explicitly after configuration and credentials are ready:

```powershell
$manager = 'C:\Users\HappyDucky02\Documents\Codex\helvetic-lens-monitoring\controller\release_manager.py'
& $python $manager --config $config --bootstrap
& $python $manager --config $config --status
Get-ScheduledTask -TaskName 'HelveticLens-Monitoring-v2-AutoDeploy' -TaskPath '\'
Get-ScheduledTaskInfo -TaskName 'HelveticLens-Monitoring-v2-AutoDeploy' -TaskPath '\'

# After bootstrap, quality gates and initial HTTPS identity are verified:
Enable-ScheduledTask -TaskName 'HelveticLens-Monitoring-v2-AutoDeploy' -TaskPath '\'
```

Record the controller revision, deployed application revision, quality-gate result,
Compose project/context, backup and restore evidence, and public HTTPS release
identity. Then publish an independently reviewed subsequent application commit to
the Monitoring branch, let the scheduled poll run, and verify that its deployed
identity changes while `helveticlens.ch` remains unchanged. A static configuration
check or a successful task registration does not establish this live acceptance.

## Updates, pause and recovery

Application updates come only from the dedicated branch. Push tested application
changes there; the pinned manager fetches and checks candidates through its release
transaction. Keep `self_update: false`: application pushes cannot update the active
controller. To upgrade the controller, review its exact commit and rerun the installer
with that SHA. Do not install uncommitted manager edits.

```powershell
# Pause future polls without stopping an in-progress deployment.
Disable-ScheduledTask -TaskName 'HelveticLens-Monitoring-v2-AutoDeploy' -TaskPath '\'

# Resume, or request one poll through the installed task.
Enable-ScheduledTask -TaskName 'HelveticLens-Monitoring-v2-AutoDeploy' -TaskPath '\'
Start-ScheduledTask -TaskName 'HelveticLens-Monitoring-v2-AutoDeploy' -TaskPath '\'
```

Inspect `--status`, state history and logs before intervening. Failed candidates
must preserve or recover the previous successful release through the existing release
transaction. A failed first bootstrap has no prior release: retain its evidence,
correct the cause and inspect all retained resources before retrying. Bootstrap deliberately refuses existing instance containers or volumes; a failed installation therefore needs an explicit, reviewed recovery or cleanup decision before a new bootstrap. Never discard retained data automatically or manufacture a deployed record.
For an operator-requested rollback, publish a reviewed revert commit on the Monitoring
branch and let the same quality/deployment transaction process it. Review database
migrations before reverting; restoring data is a separate recovery action. Never use
force pushes, reset shared state, or run `docker compose down -v` as a rollback.

After reboot, the owning user must log in and Docker Desktop must be ready. Sleep,
logout, power loss or a stopped Docker engine can interrupt this development host.
The task is not a SYSTEM service or a guarantee of unattended boot availability.
`LastTaskResult = 0` only describes the last task process; verify deployment state and
the public endpoint as well. Preserve backups independently and rehearse restoration
against only this instance before claiming recovery readiness.

## Installer regression checks

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\deploy\test-install-monitoring-auto-deploy.ps1 -PythonExecutable $python
```

The test uses a disposable local Git repository, real ACL checks on a temporary
directory, and mocked Task Scheduler calls.
It exercises real controller extraction and compilation, configuration preservation,
strict instance boundaries, controller provenance, repeat installation and task
ownership. It does not register a real task, change Docker, contact GitHub or prove
the live application deployment.
