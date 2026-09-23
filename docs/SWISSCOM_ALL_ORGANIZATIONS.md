# Swisscom Apertus 70B for all organizations

Status: VERIFYING. Owner request, 23 September 2026: use the issued remote
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
- Production activation and all-organization/concurrency checks remain pending.
