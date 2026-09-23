# Test suites and release profiles

Effective 23 September 2026, at the owner's request. The standard automatic
release no longer waits for the entire API regression suite. This replaces the
older full-suite requirement for every deployment, not the requirement to test
changed behavior before committing.

## Why the previous gate took about 90 minutes

The successful production release `6ad42edc85fa02fd647b7697c063a9135b83d9d7`
took 4,942.8 seconds in total. Its API stage took 4,693.2 seconds, including
container setup; pytest reported **5,101 passed, 18 skipped in 4,661.52 seconds**
(77m 41s). Image builds took 90.9 seconds. The slowest individual test was 14.20
seconds: the total came from thousands of serial scenarios and repeated database
and application setup, not one 90-minute stalled test. The previous session-local
empty-schema optimization helped the common HTTP fixture, but many independent
integration fixtures still create databases and run migrations.

Source: the host's retained `20260922T121602Z-6ad42edc85fa.log` and deployment
journal. These measurements concern that exact successful release.

## Three disjoint API suites

| Suite | Purpose | Command |
|---|---|---|
| Smoke | Platform startup/readiness, real migration lifecycle, authentication/CSRF, tenant isolation, persisted work, durable job dispatch and release controls | `npm run test:smoke` |
| Functional | Isolated rules, matching, evidence contracts, parsers and deterministic transport doubles | `npm run test:functional` |
| Integration | Application/API, database, worker, multi-component and remaining regression scenarios | `npm run test:integration` |

`npm run test:release` runs smoke and functional once each. `npm run test:full`
and the compatible `npm run test:api` run every API test once. Existing frontend
Node checks remain in the normal root build; the `check:*:browser` scripts remain
separate browser integration checks. Model-manager tests and permitted live
PostgreSQL/source acceptance are separate existing checks, not implied by an API
suite passing. Tests requiring an unavailable external test service retain their
existing explicit skips.

The reviewed inventory is `services/api/tests/suites.json`. A whole-file selector
or an exact unparameterized `file.py::test_function` can belong to smoke or
functional. Every other case, including new tests, belongs to integration. No
existing case is deleted or newly skipped. Overlapping selectors, missing/renamed
critical checks and a common application fixture in functional fail collection.
Each tier command collects the entire tree before selection so this validation
cannot silently reduce the release gate. Individual affected-file invocations
remain supported without `--test-suite`.

The runner uses **two pytest workers**, groups each file on one worker and keeps
the existing per-test temporary database isolation. Each worker has its own
empty migrated-schema fixture. QA containers have two CPUs, 4 GiB memory and a
bounded process count on the main host as well as configured instances. The
runner allows 0–4 workers explicitly; production uses two. Test-tool dependencies
remain outside production API images.

```sh
# Inspect selection without executing any test.
npm run test:integration -- --collect-only

# Serial diagnostic replay or a machine-readable report.
npm run test:release -- --workers 0
npm run test:integration -- --junitxml /tmp/helvetic-integration.xml

# Affected tests still run before publishing their feature.
uv run --project services/api pytest services/api/tests/test_deployment_history.py -q
```

The [pytest marker documentation](https://docs.pytest.org/en/stable/how-to/mark.html)
and [xdist file distribution documentation](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)
describe the underlying selection and worker behavior. Our inventory supplies
the product-specific classification; there is no filename guessing at runtime.

## Deployment profiles

| Profile | API checks | Web checks | Invocation |
|---|---|---|---|
| Standard (automatic default) | Smoke + functional, fail on the first failure | Existing root build checks | `python3 /srv/helvetic-lens/deploy-control/release_manager.py --poll` |
| Full | All three suites, fail on the first failure | Existing root build checks | Add `--test-profile full` to `--poll` |
| Hotfix | Explicitly skipped | Explicitly skipped; Next compilation and TypeScript still run | Exact SHA and reason, below |

Bootstrap uses full verification. An older target without the suite runner falls
back to its complete serial API gate and cannot use audited hotfix mode. A standard release records integration as
**skipped**, never passed. The administrator deployment details show the selected
profile, suites, skipped steps and emergency reason in all five interface locales.
Historical runs without a recorded profile remain unclassified.

Run affected integration checks during feature development. Use the full profile
for a new candidate when broad regression is required. Standalone full/integration
commands can also verify an already deployed revision in a development checkout;
`--poll` does not redeploy an already active SHA just to rerun tests. This change
does not install a nightly scheduler or claim that deferred integration checks
have run automatically.

## One-shot emergency installation

On the production host, after the intended commit has been pushed to main:

```sh
python3 /srv/helvetic-lens/deploy-control/release_manager.py \
  --hotfix FULL_40_CHARACTER_MAIN_COMMIT_SHA \
  --reason "Incident 123: restore access after the configuration regression"
```

Replace the SHA placeholder with the exact intended commit. The manager fetches
the trusted repository and refuses if main now points elsewhere. The reason is
required, bounded and redacted in the journal; do not put credentials in it.
The deployment lock still applies: an active release is not interrupted, and an
explicit hotfix reports that it could not start. An explicit hotfix can bypass the
retry cooldown of an already failed attempt; automatic polling still observes
that cooldown. Git history/ancestry, configuration validation, API lint,
image compilation, writer coordination,
backup, migrations, public readiness, model restoration and rollback remain in
the existing pipeline. Build or readiness failures cannot become successful
activation. The hotfix build argument only removes pre-deployment API and web
test execution, not the operational activation check.

The bypass exists only for this invocation. It is not saved in cron, an
environment variable, application configuration or a repository label. A later
automatic retry/update uses standard checks again. No actual hotfix deployment
was needed to implement or verify this feature.

## Verification — 23 September 2026

- Final standard suite: **726 passed in 35.59 seconds**, with two isolated local
  workers (68 smoke + 658 functional). These timings exclude Docker startup,
  builds and backup/activation. This is a smaller gate, not a claim that the
  entire previous suite now finishes in 36 seconds.
- **177 affected controller, journal, migration, retained-data and backlog
  checks passed in 22.93 seconds** with two workers. They exercise all three
  profiles, real durable journal transitions, rejection of a moved main SHA,
  lock exclusion, failed-test blocking, cleanup, readiness rollback and
  nonpersistent hotfix selection using disposable host/Git/Docker doubles.
- All 5,119 existing API cases are retained; 27 new policy/journal regressions
  make **5,146 total: 68 smoke + 658 functional + 4,420 integration**. Collection
  verifies the complete partition. Full integration runtime
  has not been remeasured; no unexecuted integration case is counted as passed.
- Another **29 policy/journal/backlog checks passed in 5.48 seconds**, including
  malformed history metadata and bounded, redacted emergency reasons.
- Exact API Ruff and the complete root web build passed. All **70 browser/axe
  checkpoints** passed across five locales and desktop/mobile, including 30
  profile cases, legacy history and the non-administrator boundary. There were
  no runtime exceptions or prohibited writes. Screenshots were inspected;
  incomplete accessibility results remain recorded, not certified resolved.
- Production activation is verified separately after the reviewed main push
  and idle-lock-protected controller update. No active deployment is interrupted.
