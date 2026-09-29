# Research before monitoring — 1.51

Recorded before implementation, 29 September 2026. MV2-002/020/024 remain IN
PROGRESS overall. This bounded slice is DONE within the verified scope below. Full target and human acceptance remain OPEN.

## Scope and dependencies

One simple public question starts a private, bounded exploratory episode using
the existing Investigation/research_state, branch worker, durable leases, source
snapshots, exact citation validation, provider adapters and session/access locks.
No parallel research store or engine. A versioned `/explore` entry point preserves
the explicitly consented legacy `/start` and existing recurring policies.

Exploration tests possible meanings before finalising an interpretation. Preserve
the original text. Show actual search/read progress and saved excerpts early.
After bounded research, persist an AI briefing with separately labelled tentative
understanding, exact cited findings, uncertainty and at most one consequential
clarification with evidence-backed directions. Do not stream hidden reasoning.
No medical/domain-specific example, correction or mandatory dimension is hardcoded.

An explicit choice or corrected public question starts a new bounded episode in
the same dossier, retaining the earlier briefing and sources. Revision pins and
request receipts fence stale or repeated replies. Private notes do not enter
public planning. Monitoring remains off until a usable briefing and a separate
explicit saved public-query action. Existing manual/legacy paths stay compatible.

## Source readiness

Use currently configured public search, Jev/Laya gates, permitted source reader
and workspace model. Missing access, invalid citations, provider failures and
budgets produce visible incomplete results, never fabricated briefs. No live paid
probe, new credentials, frozen evaluation reuse or private production read.

## Acceptance

- Both clients submit one question, with public-research disclosure and no daily
  policy creation. Retried starts remain atomic and private; old `/start` is intact.
- Real worker fixtures exercise ambiguous text, competing meanings, read evidence,
  exact-quote briefing validation and a consequential clarification.
- A selected direction changes actual later planning/search. Old evidence and
  interpretation remain available; stale/double replies cannot launch duplicate work.
- Silence ends the bounded episode. Partial/failing sources, model failure,
  pause/resume, session changes and no-evidence states remain honest and recoverable.
- Public-source-only briefing input and current source exclusions apply before
  and after inference and on reads; source quotations are not AI prose.
- Daily monitoring requires an explicit action after a usable brief. No old
  policies are disabled or silently rewritten.
- UI keeps source evidence, AI interpretation, research activity and human actions
  distinct. No new setup questionnaire; no classic draft setup demanded by default.
- Exact API lint, affected worker/API/access tests, backlog invariant and both
  clients' tests/lint/types/builds pass before push. Verify actual Core/Sites
  activation separately. Full target architecture and human/domain acceptance OPEN.

## Implemented contract and limits

`product_exploration.py` adds a `brief` phase to the existing durable worker.
Each episode permits four branches, depth one, 12 federated search reservations,
six source reads, 16 model requests (the final request reserved for the briefing),
40 gate reservations and 360 active processing seconds. Queue/pause time is not an
ETA. Scope, failures and unused evidence remain explicit; the complete internet is
not promised. Exhaustion is a checkpoint, not implicit permission to expand.

`POST /products/{product}/explore` requires strict public-query consent and creates
no WebResearchPolicy. The original question remains unchanged. The added JSON
state is additive; no schema migration or old-policy rewrite is required.
`POST .../investigations/{id}/exploration/reply` pins the briefing revision and exact
chosen question, or accepts an explicit corrected public question. It creates one
new run, preserves the previous briefing and reuses only currently eligible public
context. Pause/cancel can also be redirected; an episode with a successor cannot
be resumed in parallel. Lost-response replay returns the already created run.

The clients show a simple reading surface with early source passages, tentative
AI understanding, findings, conflicts/analogies, uncertainties and next directions.
Quoted passages stay separate from AI prose. Historical investigation readers
retain the saved briefing. Current-source exclusions invalidate it on read and
before persistence. The existing revision-pinned recurring-question editor is
available only after a usable briefing; the server enforces that prerequisite.
The legacy `/start`, manual setup and already enabled policies remain compatible.
Resuming the same previously enabled public question/cadence does not require a
newer exploratory episode to finish; a new question/cadence does require a briefing.

## Evidence

Both clients: 255 tests, lint, TypeScript and production Sites build passed.
23 earlier affected Core checks passed, including legacy start and iterative
research. 49 wider worker/recurring/access checks passed. All nine dedicated exploration
fixtures passed on the final episode-budget logic; three affected policy/continuation
checks passed after preserving pause/resume of previously enabled scope. These
reported test groups overlap; they are not summed as independent checks. Scripted sources demonstrate
mechanics and privacy, not live-provider accuracy or medical/legal acceptance.

## Verified production activation

Core `3b2b375f80c1f0c3b6258d71faa74350ca6625cf` activated on 29 September
2026. Legal `3b4d498dfa6254d09db7cf872e621eb82dc2018e` and Pharma
`795c2b2c650cb97216c5c60bd5181f4250fe4cb7` are published as version 50 in
their existing public Sites. Both GitHub main branches and the separate Sites
source repositories contain the exact validated source. No duplicate deployment.

[Production receipt](product-releases/2026-09-29-1.51-research-first.json):
45 exact native module hashes, unchanged schema/DomainPacks, five healthy containers
and nine native routes; 47 exact public assets and 49 HTTP/auth/origin checks per
product. A transient asset connection closure and a single gateway 502 during
verification were followed by successful fresh checks; no product data or paid
inference was used. The frozen 1.35/1.37 validation remains unopened.

Receipt SHA256: `db3d6a8853fce8b1748f57d251a68474344ed227f0bdc00a6e311dcb759eac7f`.

The standard Core release passed smoke/functional gates; affected integration
checks are recorded above. Browser QA, live-provider semantic accuracy and
professional/human acceptance are not claimed. Full architecture remains OPEN.
