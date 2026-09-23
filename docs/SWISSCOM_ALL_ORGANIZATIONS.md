# Swisscom Apertus 70B for all organizations

Status: DONE. Owner request, 23 September 2026: use the issued remote
Swisscom Apertus 1.5 70B integration across every organization and every AI
request, to test the product with several users instead of local inference.
H26-08 owns this rollout; MV2-023 receives the shared Marvin routing correction.

## Scope and dependencies

- Configure all existing organization inference records and a persistent
  production default for future organizations with the issued Swisscom endpoint
  and `swiss-ai/Apertus-v1.5-70B`. Preserve other saved provider connections.
- Propagate the complete remote connection through the common API/worker Compose
  environment. Private credentials stay in the protected deployment environment
  and encrypted organization storage, never Git, UI responses or task logs.
- Route Marvin's generative chat and remarks through the organization's active
  provider. Local execution remains available only when explicitly selected;
  remote errors must not silently fall back to a local model.
- Show remote execution and provider context in the assistant and shell across
  all five product locales. Keep conversation ownership, pause/context controls,
  source rights and the cited legal handoff. Do not log private chat prompts.
- Existing source coverage, model capability approvals and human review remain
  independent of provider routing. Deterministic navigation/evidence helpers
  do not become model calls. This is not MV2-023/MV2-051 quality-gate completion.

## Acceptance

1. Reversible, protected snapshots precede changes to deployment defaults and
   existing inference records. All existing organizations resolve Swisscom 70B;
   a newly created test organization inherits the same default.
2. API and background workers use that provider after a normal verified release.
   Marvin's runtime, chat and remarks use the same explicit organization choice.
3. Regression tests prove local/remote routing, safe failures, unchanged private
   conversation boundaries, provider disclosure and concurrent organization
   isolation. Run the required API lint, affected tests and frontend checks.
4. Bounded real-provider checks succeed for each organization, plus concurrent
   independent organization requests and an authenticated multi-user regression. Report observed concurrency, latency and any failures;
   do not infer a provider quota or general load capacity from this sample.

No user memberships, monitored laws, profiles, subscriptions or source permissions
are changed by this rollout. Existing local model artifacts are retained for an
explicit future switch back.

## Pre-release evidence — 23 September 2026

- All 160 affected API cases passed (59 routing/deployment and 101 integration,
  settings, assistant history/guidance and profile regressions): real remote adapter with synthetic HTTP,
  explicit local routing, provider failures without local fallback, default
  inheritance, concurrent authenticated users with separate credentials, private
  conversation ownership, Compose propagation and deployment validation.
- Frontend catalogue audits and shell/resource/report/help/influence checks
  passed. The isolated production frontend build and TypeScript passed.
- Candidate Marvin code was exercised against the existing Legal Hackathon
  Swisscom connection without changing serving files: a valid private chat
  response in 1.06 seconds and a valid remark in 0.31 seconds, both reporting
  `swiss-ai/Apertus-v1.5-70B`, remote execution and no local fallback.

## Verified production activation — 23 September 2026

- Automatic release `8ec8884bd048` completed at 20:22:28 UTC. Public readiness
  returned that release with healthy PostgreSQL and Redis. The release journal
  records successful configuration validation, API lint and standard release
  tests, image builds, backup, startup and public health checks. The separate
  integration suite was run locally as described above.
- Protected production environment and encrypted database snapshots preceded
  activation. All seven existing organizations now have the issued Swisscom
  connection saved and selected, using `swiss-ai/Apertus-v1.5-70B`. Existing user
  memberships, laws, profiles, topics and source subscriptions retained their
  counts. Other provider connections were preserved. Each activation has an
  administrative audit entry attributed to the authorized operator.
- The API, AI worker, CPU worker and scheduler each resolved the remote provider,
  model and configured credential for all seven organizations. The persistent
  default also supplies future organizations; authenticated registration and
  inheritance are covered by the regression test. Requests use a 90-second
  timeout, zero transport retries and batch concurrency of two.
- Fresh, non-sensitive generative assistant requests succeeded in all seven
  organization contexts: 0.660–1.117 seconds each. Four simultaneous requests
  from distinct organization contexts all succeeded, each returning its own
  marker: 0.710 / 0.614 / 0.537 / 0.525 seconds, 0.710 seconds total wall time.
  These checks made no private history writes and reported remote provenance
  with no local fallback. Authenticated two-user credential and history
  separation is separately verified by the regression test. This bounded
  sample is not a provider quota or sustained-load benchmark.
- The AI worker independently completed a fresh structured connectivity request
  through its deployed Swisscom configuration.
- The authenticated production browser showed **AI configured**, **Remote AI
  configured**, **Swisscom · swiss-ai/Apertus-v1.5-70B · remote**, the provider
  disclosure and **Personal · remote AI**. A new harmless greeting completed
  through the public site and appeared in the user's owned Marvin conversation.
  No organization roles or permissions were changed.

## Recovery and limits

The previous deployment environment is retained with owner-only access under
`~/.config/helvetic-lens/rollout-20260923/`; encrypted prior inference rows are in
`/data/operations/swisscom-all-20260923/inference-before.json` in the application's
persistent data volume. Restore only the intended provider configuration under
an authorized operator session, preserving later unrelated changes, then use the
normal release process for environment changes. Local model artifacts remain
available for an explicit selection; remote errors do not select them.

Source rights, independent model-capability approvals, legal review, and the
broader MV2-023/MV2-051 acceptance gates are unchanged. Routing every generated
request to the selected provider does not grant an unreviewed legal capability.
