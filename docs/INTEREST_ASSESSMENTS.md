# Shared event relevance briefs

HL-089 is **in progress**, not enabled in the UI. The 8 September 2026 change
provides the generation contract and transactional storage. It does not yet
enqueue enrichment after matching or attach briefs to feed/digest notifications.
The deterministic feed continues to work independently of this module.

## Contract and evidence

`interest_assessment.Dossier` is an internal complete snapshot for one organization
and one saved event. It includes every admitted interest, immutable revision and
fingerprint bindings, material source units, official facts, organization profile
facts, model/runtime configuration identity and output locale. It has no user,
private conversation, subscription or credential fields. A topic reason stays a
discovery lead; the output explicitly leaves legal relationships unassessed.

Generation returns a short explanation of what happened, exactly one reason for
each interest, profile-grounded importance, affected profile areas, one review
step or `no_action_now`, limitations and saved primary-source references. Low
importance is valid. Without organization profile facts importance must be
`undetermined`; the engine must not invent an organization or assume low risk.
Official status and dates come from the input's cited saved evidence, not model
output. Citations retain exact version/artifact/unit IDs and publisher URLs; no
copied passages or model-generated URLs are persisted in the result.

Schema validation rejects malformed/extra fields. Additional validation rejects
missing/duplicate/foreign interests, unknown or non-primary evidence, a reason
citing another interest's evidence, an event summary citing only the monitored
law, fabricated profile fields and review steps without a valid target. These
checks establish structural completeness and provenance. They **do not prove**
that prose follows from a citation, that reasoning is useful, or that a model
obeyed a language instruction. Independent semantic/local-model evaluation is
still necessary before claiming a useful AI result.

## Bounded generation

One generation and at most one schema/citation repair share a two-HTTP-call budget
(including ModelClient transport retries) and a 120-second deadline. A timeout or
external cancellation does not start a schema repair. The engine owns a copied
snapshot across awaits, so mutation of caller lists cannot change result bindings.
Local route is the default; cloud requires an explicit approved-fallback flag
supplied by the future administrator-controlled worker, never a public caller.

There is one dossier, not an inference request per topic or per user. Contract
limits are 64 interests and 64 material evidence units. The complete serialized
input and response schema must fit a configured character envelope, with repair
space reserved; otherwise generation fails before a model call. Nothing is
silently sampled or dropped. This is **not** a tokenizer measurement or a planner:
the worker must select appropriate complete material units, bind the actual
approved runtime and enforce its measured input/output context allocation. Large
organizations exceeding these limits need a documented complete aggregation
strategy before automatic enrichment; they must not receive a sampled brief
presented as complete.

## Storage and concurrency

`InterestEventAssessment` has a database-unique organization/event/input fingerprint,
an immutable manifest, lifecycle, fenced attempt identity, timestamps, structured
result, limited provider-call provenance and sanitized error category. Its
normalized `InterestAssessmentBinding` rows record exact topic, law-candidate,
direct-watch and evidence references. Historical reference IDs are deliberately
not cascading live-interest foreign keys: deleting a topic must not erase the
explanation of why a previous assessment existed. The manifest stores hashes and
references, not original passage or profile text.

`AssessmentStore.prepare` serializes reservations using the existing organization
event-admission row. Six concurrent transactions produce one assessment; only
one queued-to-running compare-and-set acquires it. Changed inputs supersede
unfinished assessments. The old attempt token cannot publish after supersession,
failure or a later attempt. Successful results are immutable and reusable only
by exact fingerprint; reads never schedule or generate. Failed generation needs
an explicit retry, bounded to three attempts. Raw provider exception strings are
not stored because they may echo credentials or document content.

The repository neither commits nor calls a model: the caller commits reservation,
closes the transaction, then generates and commits completion separately. It
checks organization ownership and event admission even in privileged sessions.
The existing session policy also scopes both new tenant tables.

## Required next integration

The repository is **not** a public admission API. Before prepare, retry and finish,
the matching worker must assemble and revalidate all current topic/law/watch
revisions, evidence visibility, event status, profile and approved runtime; it
must exclude stale, muted, rejected, expired and below-threshold candidates.
An event-admission row alone is not enough to prove those inputs are current.

Still required under HL-089:

- Complete current-input assembly and measured material-unit planning, including
  organizations with more interests than one dossier can fit.
- Durable job IDs, automatic matching trigger, quotas, priority/fairness,
  cancellation recovery, backoff/dead-letter handling and guarded reactivation of
  a previously superseded fingerprint; no caller may bypass currentness checks.
- Full per-attempt/token/runtime diagnostics and append-only feedback history.
- Exact-key freshness across feed, notification, digest, history and assistant
  readers, with honest pending/failed/not-scheduled presentation and bounded waits.
- Administrator-only prompt/fallback policy integration and evaluation of useful
  reasoning, grounding, output language, noise and target-hardware latency.

## Verification

On HappyDucky02, 104 combined regressions passed in 90.67 seconds, including 52 new
contract/storage scenarios. The fixed contract corpus spans all five locale
instructions and four event kinds; model answers are deterministic test doubles,
not native-language or real-model quality evidence. Real SQLite transactions
exercise reuse, stale completion, retry, tenant isolation and six-way concurrency.

Seven isolated PostgreSQL 17.11 scenarios also passed: reuse, supersession, retry,
privileged-session scope, concurrency, invalid-result rejection and migration
roundtrip. The new Alembic head is `d7d9f1284ba5`; upgrade/downgrade preserves
pre-existing corpus/topic records and recreates the required constraints/indexes.
Downgrading deliberately removes the new assessment tables and their records.
No working or production database was migrated, no external AI was called and
no notifications were sent. No UI/build/browser improvement is claimed here.
