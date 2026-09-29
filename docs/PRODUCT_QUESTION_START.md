# One question to a living dossier — 1.48

Status: VERIFYING publication. Owner priority recorded before code, 29 September 2026.
Scope: MV2-002/020/023/024. This takes priority over requested-source Coverage work.

## Product outcome

Legal and Pharma open on one question, without a required title, template,
sector, topic selection, source list or model choice. One clearly disclosed
Start research & monitoring action creates the private dossier, queues existing
iterative research, enables the existing daily public-question policy from the
next day, and follows in-app updates. No email, publication or private-document
search disclosure is enabled. The question drives real search/planning; optional
recordkeeping fields are not presented as prerequisites or hidden search controls.

Reuse Core ProductDossier/LegalMonitoringProfile, Investigation, bounded iterative
engine, WebResearchPolicy, PrivateDossierFollow, jobs, current organization locks,
source rights and access. No new data store/migration/provider or fake source pack.
The legacy profile stays draft/private; this is not a claim that native topic
monitoring has activated. Actual recurring-research state must be shown separately.
Use existing server research defaults and policy limits; no new inference study.

## Acceptance

- One strict, authenticated/CSRF-protected atomic start endpoint with explicit
  recurring-public-question consent. Trimmed 5..300 character question; derived
  title and product-specific existing domain pack. Reject unsupported fields.
- Creation, queued investigation, daily policy, following and consent receipt are
  one transaction. Retries return the same current records; changed question/key
  collision, foreign ownership, current read-only role and revoked sessions fail.
  A replay never reenables a paused policy or starts another job. Queue failure
  rolls back all new records. Next-day scheduling avoids a duplicate immediate run.
- Both products run the existing real worker against scripted local fixtures;
  no paid probes or live medical/legal assertions. Prove scheduler waiting,
  recurring updates, pause controls, limits, no extra acquisition on mere reads,
  and retained private/public boundaries.
- Homepage directly exposes the question. Authentication preserves typed text.
  No mandatory title, engine, routing, budget or checkbox questionnaire. The action
  explains public provider use, daily checking and in-app updates before submission.
  Lost-response retry preserves the exact request identity and question.
- Show actual daily research state with an immediate pause/resume control; errors
  or missing provider configuration are not described as successful checks.
  Topic-profile draft state must not imply all monitoring is off.
- Existing custom setup remains optional. On dossier reading, optional template/
  subject metadata is folded and explained as recordkeeping. Findings appear before
  saved-evidence search controls. Preserve all existing review, history, privacy,
  exports, source citations and deep links; do not hide nine native Monitoring routes.
- Required checks: affected Core tests and exact lint/backlog invariant, both-client
  interaction/render tests plus full tests/lint/types/build. Push tested main and
  deploy exact artifacts to existing public Sites; verify Core and client activation.

## Limits

The screenshot at ai.helveticlens.ch is a separate client, not native helveticlens.ch.
This scope changes shared Core and the Legal/Pharma clients from this thread; the
optional scope question asks whether to change that separate client as well.
No source-coverage completeness, professional advice, automatic claim acceptance
or guaranteed answer is implied. Daily recurrence uses the existing bounded search
contract. Advanced template/context-to-Ask integration and domain review policy
remain separately tracked, not hidden behind a claim of magic.

## Implemented behavior and verification

The shared `/api/products/{product}/start` contract writes one private profile,
dossier, iterative investigation/job, next-day daily policy, in-app follow and
explicit disclosure receipt in one transaction. No migration is needed. The
profile remains creator-private; `research_monitoring` exposes the actual policy
independently of the legacy topic state. Current membership, write origin/CSRF,
owner access and strict public-query consent still apply.

Both clients use the same one-question component at the research desk. The typed
question survives in-place sign-in. Initial submit, concurrent clicks and lost
response retries reuse the same request identity; no question enters the URL.
The dossier shows current public-research readiness with pause/resume, folds
recordkeeping fields, points to research instead of the old setup questionnaire,
and puts investigation findings before saved-evidence search. Optional manual
topic/source setup and all existing citations/reviews/deep links remain.

Local verification exercises the actual worker and scheduler with scripted public
source/model fixtures for both products, then checks private updates, recurring
acquisition and pause/replay. It does not call paid providers or create private
production records. 65 Core cases passed (64 integration, one backlog smoke); exact API lint passed.
Each client passed 239 tests, lint, typecheck and the production build. Shared-file
parity and protected-value checks passed for all three repositories. Exact production
activation is pending at this checkpoint. The existing frozen provider studies remain closed.
