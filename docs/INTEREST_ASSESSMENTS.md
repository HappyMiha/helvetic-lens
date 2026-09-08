# Shared event relevance briefs

HL-089 is **in progress**. The 8 September 2026 changes
provides the generation contract, transactional storage, measured local execution
and current-input admission, including material evidence from existing saved
legacy comparisons. Complete passage sets remain the fallback when no comparison
exists and they fit the contract. The feed now offers an on-demand saved-brief
reader. Matching can now enqueue measured admission through explicit operator
opt-in and independent local approval. Web previews and digest delivery now reuse
validated saved briefs in the recipient's language (see the digest section below).
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

The repository is **not** a public admission API. Workers can now use
`AssessmentStore.prepare_current` and `finish_current`, backed by
`interest_admission.assemble`, rather than supplying interest lists themselves.
The raw storage primitives remain internal; an event-admission row alone is not
enough to prove inputs current. Runtime resolution and durable execution are
implemented below. The operator-controlled matching trigger is described below;
administrator UI controls and reviewed model approval remain required for rollout.

### Current saved-input admission — 8 September 2026

Assembly traverses all current topic matches in 100-row candidate batches, not
the feed's five-item preview. Saved evaluation/rule fingerprints, current topic
revision, expiry and current rejected/muted decisions are rechecked by the same
topic validity reader. Active direct watches and active, unexpired, current-rule
law candidates are included alongside topics. Dismissed/expired deliveries,
rejected organization reviews, paused watches and cross-work source versions do
not qualify. More than 64 admitted interests fails explicitly, without a sampled
brief. Traversal also continues after a whole batch of stale candidates.
Law retrieval scores and reasons are recomputed from current saved facts without
rewriting candidate history; a current rule label alone cannot preserve a lead
whose actual source signals were corrected or withdrawn.

Both native and legacy evidence require the current organization's grants, the
correct work/language identity, accessible legacy parents, saved original-file
identity, publisher URL and unambiguous passage IDs. All saved passages in each
selected document are included; repeated law references reuse its evidence units.
An old monitored-law version cannot be enriched after a newer version of that
expression is saved: its candidate needs rechecking first. Missing originals'
identity or missing citable passages leaves the event unenriched; a metadata-only
retrieval lead cannot become a primary document conclusion. An artifact key
identifies the archived original; admission does not read/verify its file bytes.

This whole-saved-passage fallback is **not a material-change planner**; the saved
comparison path added below is distinct. At most
64 evidence units fit the contract, with 16,000 characters per unit. Oversize or
malformed inputs fail without truncation. Admission and execution share the same
character-envelope preflight (including schema and repair allowance), and an
unapproved cloud route is rejected before creating queued assessment storage.
Characters are not measured tokens; the worker must still bind the actual runtime
and measured tokenizer/context/output allocation before model execution.

Without an eligible saved comparison, the dossier explicitly tells the model
that no complete before/after comparison has been assembled. Independently cited
official status/date facts are not assembled in either path yet. It
must not invent changes, enactment, repeal or deadlines from current wording.
The result also preserves these input limitations and the recorded event type
as server-bound fields, independently of the model's uncertainty text.
Binding those facts and a deterministic material comparison remains open; this
slice does not claim a complete change explanation for every kind of event.

Profile facts include only this organization's description and business areas,
never another profile, personal read/mute state, chats or subscriptions. Empty
profile facts require undetermined importance. Input fingerprints include exact
membership, names, source text/artifact identities and revisions, profile content,
locale, prompt and caller-resolved model/runtime configuration. Reused ORM sessions
reload committed external edits before assembly.

Before publication `finish_current` reassembles the dossier and compares its key
with both the generation input and reserved record. Changed or revoked inputs
supersede only the matching running attempt; stale tokens cannot write results.
Completed history stays immutable. The caller commits each short transaction and
performs inference outside it. This is not a globally frozen database snapshot:
readers must recompute an exact current key rather than asserting freshness from
the `succeeded` status alone. Fresh assembly currently does per-law lookups and
scans stale topic candidates; no bounded query-work or target capacity claim is made.

### Measured local execution — 8 September 2026

`LocalBriefRunner` now connects current-input admission and fenced storage to the
real `ModelClient`. It authorizes the event before contacting inference, observes
the actual local runtime, and requires an independently reviewed `interest_brief`
grant for the exact immutable model/runtime/hardware identity and output locale.
An Ask or impact-report grant does not approve organization relevance briefs.
No production approval was added: synthetic approvals test the mechanism only.
Unapproved profiles leave saved deterministic event evidence available.

The complete system message, serialized dossier, response schema and generation
parameters are measured through the local runtime's tokenizer endpoint before
reserving new work. Both the physical context and the reviewed input/output/safety
allocation must fit. ModelClient verifies the request hash and deployment pin,
remeasures each generation (including repair), and validates its response budget.
No omitted passages, silent cloud fallback or per-interest generation is used.
Tokenizer requests are separate metadata calls, not counted as model generations.

One shared two-generation budget includes transport retries and the single JSON/
citation repair. A 120-second async deadline includes runtime probing and model
calls. Database connections are not held while awaiting HTTP. Synchronous input
assembly remains subject to the DB's own query/lock behaviour; this is not a
measured end-to-end 120-second SLA or target-host capacity result. Background
priority is sent to the gateway; per-organization fairness and durable job quotas
are not implemented by this internal runner.

Before publishing, the runner observes the runtime and approval again, then
reassembles current organization inputs. Changed sources/configuration supersede
the attempt; unavailable/revoked runtime approval fails it without accepting a
result. Cancellation and timeout close the claimed attempt with a safe category.
Hard process termination still requires durable lease/recovery integration.
Concurrent callers reuse a running attempt. Successful exact inputs are reused
after a current-runtime lookup, with no tokenizer or generation calls; restarting
the same immutable model does not force regeneration. Failed or superseded records
are not automatically retried by a read.

Successful storage includes a bounded, validated execution proof: runtime and
capability fingerprints, admission and generation token measurements, duration
and call limits. It excludes raw prompts/provider bodies and rejects unexpected
fields or measurements from a different launch. Transport diagnostics remain in
the existing integration log. Failed attempts currently preserve the safe error
category rather than a complete per-attempt execution ledger.

This is an internal execution adapter, **not yet a scheduled product feature**.
No route, matching trigger, notification renderer or page load invokes it yet.
Official facts and before/after material planning remain separate prerequisites;
the existing input limitations continue to be stored in every accepted result.

### Complete saved-comparison material dossier — 8 September 2026

For an event whose source has a legacy Version mapping, admission now uses its
existing saved before/after comparison when the baseline is explicit or
unambiguous. The organization's selected monitoring baseline takes precedence;
without one, multiple distinct saved baselines are an actionable ambiguity, not
an invitation to choose by import timestamp. Multiple modes for the same exact
pair share the same baseline; one stable saved record is selected and validated.
No baseline is inferred from effective dates, source filenames or model output.

The planner audits the **entire persisted v6 diff** against both current saved
passage collections: exact side records, positions, unique IDs, cardinalities,
classification flags and complete counts. A changed, incomplete, old-schema or
misbound comparison fails before generation, including corrections to an unchanged
passage that would otherwise be omitted from AI input. This read path does not
silently recompute or overwrite comparison history; a stale diff needs rebuilding.

All substantive, added, removed and uncertain units are included, with explicit
`before`/`after` versions. Enclosing title/chapter/section/article/numbered-clause
context is taken from exact source positions, deduplicated and labelled `context`.
Unchanged bulk and deterministic presentation-only moves, renumbering and wraps
remain in the saved audit, with counts retained in the dossier. This is structural
classification by the existing diff engine, not proof that movement has no legal
consequence. Uncertain changes are not silently treated as formatting.

A zero-material-change comparison has an empty change list and one explicitly
labelled current-source context anchor; it never fabricates a changed paragraph.
Every actual change and necessary parent context must fit the existing 64-evidence
unit, character and measured-token budgets. Oversize material changes still fail
as a whole, without ranked sampling or thousands of per-chunk requests. Monitored
target laws currently remain whole saved passage sets, so those can still exceed
the budget. Native-only catalogue versions still need an explicit persisted
comparison/baseline contract; they do not acquire one by guessing chronology.

Both legacy versions must belong to the visible same law already bound to the
event's work. Imported baselines do not require a new native mirror just to read
them: the existing Version/Law ownership rules apply. When a mirror exists it must
agree with the exact expression; conflicting known artifact languages are rejected.
Existing document-assignment checks reject mismatches and require current recorded
confirmation for unknown assignments. Unknown language or title-based assignment
is not an independent identity certification. Original identity and publisher URL
are still required; this path does not verify archived file bytes.

The v3 dossier/result retains the server-bound comparison ID, source versions,
algorithm/diff fingerprint, full counts, material-pair references and context IDs.
Validators reconcile counts with both complete version lengths and enforce each
citation's side. These fields are not generated by the model. Current-input keys
include all source passages and the full diff fingerprint, so an input correction
or changed baseline supersedes a running brief. The real local execution adapter
uses the compact complete-change request with the same preflight/repair budgets.
The output explicitly distinguishes saved comparison order from legal chronology;
official status/date binding remains absent rather than inferred from wording.

## Explicit native comparisons

`native_comparisons.select_baseline` is an internal transaction boundary for an
organization's explicitly chosen native before/after pair. It requires the event
to be admitted, both versions to be accessible under the same canonical work and
known-language expression, complete saved passages, original artifact identities
and source URLs. Both must be native: mapped legacy sources continue through their
existing assignment-confirmation path. Import time, discovery order, URL sorting,
model output and metadata dates never choose a baseline or assert legal chronology.

The `d8eaf2395cb6` migration adds organization-scoped `NativeDocumentComparison`
and `NativeEventComparisonSelection` tables. Comparisons persist the entire v6 diff
and both exact source fingerprints. A separate revision-checked selection points
to a comparison; changing/clearing it retains earlier comparison records. A clear
leaves a revision tombstone. Concurrent editors cannot silently overwrite a newer
selection. Re-saving an identical pair does not change the input key or invalidate
an existing reusable brief. Changed source inputs create a new saved comparison
instead of rewriting the old one. Failed selection writes roll back their savepoint.

Native event admission now follows that selection, checks current access and both
source fingerprints, audits the complete persisted diff, and supplies all material
changes plus exact ancestor context through the existing measured local runner.
The result records `basis=organization_selected`, exact before/after version IDs
and the comparison ID. Missing selection retains the existing explicit
whole-document-only behavior; a stale or inaccessible selected comparison fails
closed rather than silently falling back. Publication rechecks the selection,
source evidence and all ordinary dossier inputs. Oversized complete diffs can be
saved for review but cannot be silently sampled to fit the 64-unit brief envelope.

The registry now links native events to `/native-comparison/{event_id}`. Its
organization-authorized API exposes candidate snapshots, revision-guarded save/clear
and paged material or all-passage comparisons. Organization viewers can inspect
the saved comparison but cannot change the shared baseline; writes require the
existing actor and CSRF checks. No source snapshot is automatically assigned a
predecessor, and selecting a baseline does not launch AI or a matching job.
An operational connector policy must separately
justify any official predecessor relationship. Archived artifact bytes and legal
identity/chronology still need their independent verification. Downgrading this
migration removes its new selection/comparison tables, not the original corpus.

Still required under HL-089:

- Extend current-input admission with official facts and
  verified connector predecessor policy, complete large material/target-law planning and organizations with more
  interests than one dossier can fit.
- Automatic matching trigger, administrator quota policy, priority/fairness,
  operational dead-letter review and guarded reactivation of
  a previously superseded fingerprint; no caller may bypass currentness checks.
- Full per-attempt/token/runtime diagnostics and append-only feedback history.
- Exact-key freshness across feed, notification, digest, history and assistant
  readers, with honest pending/failed/not-scheduled presentation and bounded waits.
- Administrator-only prompt/fallback policy integration, actual profile approval,
  and evaluation of useful
  reasoning, grounding, output language, noise and target-hardware latency.

## Durable local jobs — 8 September 2026

`HelveticLens.enqueue_interest_brief` / `LocalBriefRunner.schedule` perform the
actual runtime/capability/token admission without generating text. A short
organization-serialized transaction saves the exact assessment and one existing
`Job`/`OutboxMessage` together. Failed admission rolls back both. The payload holds
only assessment ID, input fingerprint and locale; it contains no source text,
prompts, credentials or personal notification state. Exact success reuses the
saved result. Repeated admission coalesces; it does not automatically retry failed
or cancelled work. The ordinary durable job controls remain the explicit retry path.

New work uses `ai_background` and the existing local gateway's background priority.
Admission permits at most four unfinished brief jobs per organization and twenty
new jobs in a rolling 24 hours. Existing exact work does not consume another slot.
A new input cancels unfinished jobs whose assessments were superseded, retaining
their history. These conservative fixed limits are not a measured capacity claim
or a complete fairness/high-confidence-priority policy for 100 organizations.

The Celery service execution path recognizes `interest_event_brief` and delegates
to `BriefJobs`. It validates the job/assessment/event/locale binding, observes the
current approved runtime and reassembles the complete current input before any
generation. A queued fingerprint cannot silently become a different dossier.
Every claim/publication checks organization, worker, attempt and lease timestamp,
including reuse of the same worker name. A two-second heartbeat detects cancellation
or lost ownership and cancels an outstanding model await. No DB session is held
across inference. Completion stores the assessment ID, not another copy of its text.

Transient failures have bounded backoff and at most three durable attempts, each
retaining the existing two-generation-call/120-second budget. Invalid output,
unsupported evidence and approval failures terminate without automatic repeated
generation. Even an explicit job retry cannot exceed three assessment generation
attempts. Recovery fences a crashed worker's assessment token before trying again.
Final failure, cancelled queued work and exhausted lease recovery close their exact
unfinished assessment too; successful history is not rewritten.

The common dispatcher now locks job before outbox, skips locked work, does not
overwrite a running lease and respects the job's delay even if an older pending
message was available earlier. This matches worker/recovery lock order and avoids
an outbox/job lock inversion. Duplicate broker delivery remains harmless at claim.

Automatic matching admission, priority/fairness policy, administrator prompt policy,
large-dossier planning, exact-current feed/digest readers and independent model/
hardware evaluation remain required. No public route or matching trigger is enabled
by this internal execution stage, and no shipped model profile was approved.

## Exact-current saved brief reader — 8 September 2026

`GET /api/interest-feed/events/{event_id}/brief?locale=en` authorizes the event for
the current organization, including viewers, before probing runtime metadata.
No saved history in the requested language means no probe. Otherwise the local
runtime observation is bounded by the existing two-second deadline; no token
measurement, completion, queue reservation or cloud call occurs on a read.

The reader rebuilds the current dossier and requires its exact saved fingerprint.
Changed source, interests, profile, locale or model approval cannot make an older
answer current. Stored output is validated again against the dossier, including
citations, official facts, runtime proof and bounded provider-call provenance.
Unavailable, stale, pending, failed or unverifiable results do not expose old text
as current. Historical records remain unchanged. Current saved-source grants
determine native/legacy evidence links; model-generated URLs are never accepted.

Each feed card has a collapsed, full-width panel. Only opening it reads a brief;
there is no per-card background polling or automatic generation. Refresh rechecks
currentness without reloading the page and hides previous text while checking or
after failure. Five-language guidance distinguishes unavailable AI from low
importance. Explanations, organization importance, exact citations and one review
step are visible; per-interest reasons and limitations expand separately.
Technical input limitations retain their original English language annotation.

This is not automatic enrichment, a history browser or digest integration. No
real model/task/language approval ships with this slice. Rebuilding a dossier on
demand is not a measured 100-user capacity guarantee or a globally frozen database
snapshot. Independent semantic, native-language and usability review remains open.

## Matching-triggered admission — 8 September 2026

Set `INTEREST_BRIEF_AUTO_ENABLED=true` and `INTEREST_BRIEF_AUTO_LOCALE` to one of
`de`, `fr`, `it`, `rm`, `en` consistently on the API, workers and scheduler. The
default is off: this does not approve a model or enable cloud fallback. A local
profile with independently reviewed `interest_brief` approval for the selected
language and a running, measured runtime is still mandatory. These are operator
environment settings, not yet organization controls in the admin UI.

Live matching saves one admission job after exhausting its topic cursor. Each
topic-history batch saves its complete event-ID set (at most the existing 5,000
event batch bound), not just a preview. Matching output, checkpoint and admission
outbox commit together; rollback/replay cannot lose or duplicate that handoff.
The trigger fingerprint and explicit organization admission bind each batch.
Matching does not contact the model, tokenize passages or generate text.

An `interest_brief_admission` job processes one event per delivery, rechecking
current evidence, policy, locale, runtime and approval before the existing
measured runner reserves the separate generation job. It yields between events.
Only IDs, fingerprints, cursor counts and sanitized per-event outcomes are kept;
no passages, private conversations or credentials are copied into these jobs.
Missing/expired interests, unavailable evidence, ambiguous baselines and oversized
complete dossiers are recorded as limitations without preventing later events.
Source evidence/feed matching remain available if AI admission fails.

Lease owner, attempt and lease timestamp are fenced before and after token
measurement; a heartbeat cancels blocked measurement on cancellation. A crash
after generation reservation but before cursor commit reuses that reservation.
Duplicate delivery cannot create another generation. Cancellation stops later
admissions; already committed generation jobs retain their independent lifecycle.
Failed saved assessments are reported, never automatically regenerated merely
because another topic batch refers to them.

Existing generation allowances remain four pending/twenty new jobs per day per
organization. An allowance failure defers the same event five minutes without
consuming a failure attempt or advancing its cursor. Transient runtime errors
have bounded retry; invalid policy/approval/checkpoints terminate with an explicit
job error. Operator retry resumes the committed cursor and preserves outcomes.
Successful admission means the batch was examined, not that every AI result was
generated or useful. The saved feed reader exposes only exact-current successes.

Still open: admission queue capacity and priority benchmarks, automatic refresh for edits outside a
matching run, catch-up after enabling/changing policy, digest/notification reuse,
large-dossier aggregation and independently approved model usefulness. No real
model, production deployment or notification was enabled by this change.

## Saved review focus

Organization admins can edit the optional shared relevance-brief review focus on
`/prompts`; platform admins set the inherited default on `/prompts?scope=platform`.
The field accepts up to 4,000 characters. Empty means the built-in brief prompt;
an organization override uses its own complete prompt configuration, while reset
restores the platform default. Saving or resetting never calls the model.

The additional focus is composed with the server-owned evidence/output contract,
then used unchanged for exact token measurement and generation. It participates
in the immutable assessment key. Changes withdraw old answers from the current
reader without deleting history. Queued work and in-flight publication recheck
the saved focus; stale work cannot publish a result as current. Existing identical
built-in results remain reusable. This is not a promise that every model obeys
custom instructions: schema, citation and evidence validation remain mandatory.

Older API clients omitting the new field preserve the effective saved focus;
explicit empty clears it. Organization prompt revisions remain monotonic after
reset and resave, with short organization locking on save/reset. Changing a
prompt does not automatically enqueue replacement work; catch-up/refresh policy
remains open. No database migration or inference capability approval is added.

## Persisted model settings during work

Service-created admission/generation runners compare their captured public model
configuration with the current organization record before any runtime contact,
after runtime observation, after token measurement, and before publication.
Provider, endpoint/model, generation parameters, context/output limits and selected
review profile are answer-affecting. Credentials, retries, timeout and transport
concurrency do not by themselves invalidate a reusable answer. Runtime artifact
and independent approval checks remain separate and mandatory.

A stale service snapshot fails before spending tokens; a change during generation
supersedes only that worker's exact running attempt. An old worker cannot overwrite
a replacement attempt. Read paths recheck persisted settings around their bounded
metadata observation, returning `not_current` without an answer if settings changed.
History remains intact. No connection is held during model HTTP, no configuration
is rewritten, no cloud fallback is enabled, and no replacement generation is
implicitly started. A new job uses a fresh organization runtime. Embedded callers
constructing LocalBriefRunner directly may provide their own configuration reader;
without one, the runner checks the supplied client's live settings only.

## Verification

The durable execution stage passed 162 combined regressions in 192.60 seconds,
followed by 34 final job/execution regressions in 65.62 seconds after synchronizing
terminal assessment state. The PostgreSQL-only row-lock test is skipped in SQLite,
not simulated as passing. Nine final PostgreSQL 17.11 suites exercised roundtrip,
crash recovery, dispatch/backoff, same-owner lease replacement, supersession,
concurrent admissions, four separate connections, dispatcher lock ordering and
exhausted recovery. Both disposable labelled loopback/tmpfs containers were removed.
These use actual DB/local-gateway code with synthetic model approval/responses;
there was no live Redis/Celery delivery, real model inference, production restart,
notification, UI change or target-host performance certification.

On HappyDucky02, 104 combined regressions passed in 90.67 seconds, including 52 new
contract/storage scenarios. The fixed contract corpus spans all five locale
instructions and four event kinds; model answers are deterministic test doubles,
not native-language or real-model quality evidence. Real SQLite transactions
exercise reuse, stale completion, retry, tenant isolation and six-way concurrency.

Seven isolated PostgreSQL 17.11 scenarios also passed: reuse, supersession, retry,
privileged-session scope, concurrency, invalid-result rejection and migration
roundtrip. The foundation's Alembic revision is `d7d9f1284ba5`; upgrade/downgrade preserves
pre-existing corpus/topic records and recreates the required constraints/indexes.
Downgrading deliberately removes the new assessment tables and their records.
No working or production database was migrated, no external AI was called and
no notifications were sent. No UI/build/browser improvement is claimed here.

The current-input path additionally passed eight PostgreSQL 17.11 scenarios:
current reuse, law/direct-watch evidence, tenant isolation, traversal beyond 100
stale candidates, 65-interest refusal, reused-session refresh, an interest arriving
during generation, and corrected metadata withdrawing law relevance. The scratch
database was freshly recreated per scenario only in a labelled, loopback-only,
tmpfs test container. The container was removed after verification.

The local execution adapter passed 261 combined regressions and 33 final targeted
scenarios. Five additional PostgreSQL 17.11 executions verified complete measured
request/reuse, no connection held across HTTP, changed-input publication fences,
one repair and cancellation persistence. These use actual ModelClient and database
code with synthetic gateway responses and synthetic independent-review artifacts;
they prove neither real semantic quality nor target-GPU performance. The shipped
capability registry remains unapproved pending actual review.

The material comparison integration passed 190 combined regressions, 34 final
targeted cases and five PostgreSQL 17.11 scenarios. A 400-passage pair with one
modified unit produced two exact source units in one actual ModelClient generation
against a synthetic gateway response. This proves pipeline shape and binding,
not actual tokenizer size, semantic quality, legal completeness or GPU latency.

Native comparisons passed 200 combined regressions, 31 final targeted scenarios
and eight PostgreSQL 17.11 suites:
complete 400-unit comparison, selection history/clear, concurrent editors,
migration roundtrip, privileged tenant isolation, actual local-runner reuse and
selection change during generation and caller-owned rollback. SQLite's legacy
savepoint auto-commit behavior is explicitly prevented by a real outer transaction;
two concurrent writers retain the revision guard. The PostgreSQL container used only tmpfs data
and loopback port 55521, and was removed afterward. These remain synthetic model
and provenance fixtures, not an operational connector policy or legal review.


## Organization automatic-brief settings

Organization admins manage `/settings` → **Automatic shared AI briefs**. The
persisted policy selects enabled/disabled and lower per-organization generation allowances: 1–4 pending jobs and
1–20 newly created jobs in a rolling 24 hours. Cancelled/failed new jobs still
consume that daily allowance. These are bounds, not throughput promises. Existing
environment enable/language settings remain the fallback until the first explicit
organization save; the migration itself does not enable any tenant.

GET/PATCH `/api/settings/interest-briefs` returns policy revision, usage and hard
limits. Auth, tenant scope, admin-write and CSRF rules apply. Writes hold the
organization lock and compare the supplied revision; concurrent editors receive
409 instead of overwriting each other. Saving settings makes zero inference calls.

A changed policy cancels outstanding admission cursors and policy-bound automatic
generation. Workers recheck the exact saved revision/values before admission and
publication; a completion from obsolete work is not published. Completed results
remain in history. Explicit unbound/legacy generation jobs retain their lifecycle.
No backfill, model approval, automatic cloud fallback or notification is triggered.
New matching batches use the saved policy. Missing independent model approval still
blocks generation even with the checkbox enabled.

The feed requests the **user's selected language**. Without an explicit API locale,
the authenticated user's preference is used, then browser/default locale. An admin
cannot override users' language from the policy form. New matching batches enqueue
one admission per distinct active member language (at most five), coalesced across
users. In organizations without active members, the existing configured fallback
language supports non-authenticated development/legacy operation; it is not a
user-display override. The returned `language_jobs` list describes all admissions;
legacy `job_id` remains the first admission ID.

Saved variants are shared only within the same organization, inputs and language.
French work cannot supersede a German queued/running result merely because its
locale differs. All variants share the same organization quotas and require their
own language-specific model approval. Each variant is a grounded assessment, not
an unvalidated automatic translation. Changing the UI language never invokes the
model. If that variant has not been saved or cannot be validated, the panel shows
its explicit unavailable/pending state rather than silently substituting another
language. Catch-up after a new member or a preference change remains future work.

The five-locale responsive form preserves edits on failed saves, offers an explicit
reload after a revision conflict, and remains read-only for viewers. Independent
native-language review (especially Romansh), real-model usefulness, global admission
capacity/fairness, catch-up/refresh and downstream delivery reuse remain open.


## Explicit request in the user's language

When a saved current variant is missing, Today offers **Prepare in my language**.
This is an explicit POST, never a side effect of reading, refreshing or opening a
card. It also lets a user request an older development after changing language;
it does not scan/backfill every historical event. Both admins and viewers may
request under the organization's enabled policy. Viewers still cannot alter model,
prompt or policy settings. Authentication, CSRF and admitted-event checks apply.

`POST /api/interest-feed/events/{event_id}/brief/requests` accepts a UUID
`request_id` and optional supported `locale`; the default is the user's saved
language, then browser/default locale. The response is 202 with a durable admission
`job`, `reused`, and `ai_calls: 0`. HTTP performs no runtime observation, token
counting or inference. It reuses active explicit requests for the same tenant,
event, language and policy revision. An identical original UUID reuses its job
also after completion; a new explicit UUID permits a fresh admission check. A
request coalesced onto another UUID's job is not an independent durable receipt.

There are organization-wide request limits of eight nonterminal explicit
admissions and forty created explicit admissions in a rolling 24 hours, checked
under the organization lock. Reusing an existing request does not consume another
slot. All subsequent generation still shares the existing organization generation
limits (at most four pending and twenty new jobs/day). These intake limits do not
claim global scheduling fairness or a hardware throughput guarantee.

The existing worker validates current interests/evidence, model/language approval,
complete token budget and policy before reserving generation. An exact successful
assessment is reused; failed saved assessments are not silently regenerated.
Different locale variants remain independent. Revocation or disablement stops
old requests through the same durable guards; source evidence stays available.

The UI follows admission then generation using existing job observation, disables
repeat clicks while active, retains the UUID across uncertain HTTP failures and
refreshes the saved card on completion without reloading the page. Failure retains
source access and task details. The explicit action is not offered for a saved
failed assessment; operator retry remains separate. Reading old events never
substitutes another language or triggers bulk historical AI work.

## Explicit failed-brief recovery

### Server-wide generation capacity — 9 September 2026

Every new durable `interest_event_brief` job passes organization quotas and the
shared host limit in the transaction that persists its assessment/job/outbox.
`INTEREST_BRIEF_GLOBAL_MAX_PENDING` defaults to 16 (range 1–1000);
`INTEREST_BRIEF_GLOBAL_MAX_DAILY` defaults to 200 (range 1–10000). Operators must
apply identical values to all API/worker processes sharing the database. These
are conservative configurable admission bounds, not measured hardware capacity.
Organization administrators cannot override the host limits in prompt/profile
settings. Changing these environment values requires a separate planned restart.

Pending includes queued, dispatched, running, retrying and waiting-for-model
generation jobs across organizations. Daily counts new generation jobs created
in the preceding rolling 24 hours, including failed/cancelled/completed jobs.
Finishing or cancelling releases pending capacity but does not refund daily
admission. Exact job/result reuse creates no new admission. A bounded explicit
retry of the same failed job reacquires pending capacity without charging a new
daily job or resetting cumulative assessment/manual-retry budgets.

PostgreSQL takes transaction advisory lock `(1212958030, 8901)` after the caller's
organization write lock. Inside that critical section only aggregate cross-tenant
counts are read; no other organization is locked and no tenant data/counts are
returned. Job creation or retry commits before releasing the lock. SQLite's
organization UPDATE already serializes writers. Rollback releases the lock and
creates no assessment/outbox reservation. No inference/network wait holds it.

Full capacity uses the existing `interest_queue_limit` state: the admission worker
retains the current event checkpoint and defers five minutes without consuming
its failure-attempt allowance. Manual retries remain explicit and leave the prior
failure receipt untouched if denied. Lowering a limit does not cancel existing
jobs; it prevents additional admission until usage falls below the new value.

This is not a cap on metadata/token-measurement calls or other task types, nor a
replacement for per-request measured token/call limits. Global token accounting
and target-host latency remain separate work. Durable tenant rotation and aging
now use the bounded handoff described in `ARCHITECTURE.md`. Admission jobs may
wait; all saved evidence stays readable.

Today shows a localized failure explanation, cumulative attempts, exact job
details and an explicit retry for organization admins. Viewers can inspect the
state/history but cannot invoke the existing admin-only job retry route.
The button requires enabled organization policy. A retry queues background work
even in inline development mode; the HTTP request never performs inference.

The existing `/api/jobs/{job_id}/retry` path now validates the exact organization,
event, assessment fingerprint, language and generation-job binding before
resetting a failed brief. Organization locking coalesces concurrent retries.
There are at most two manual retries and three cumulative assessment attempts;
resetting the generic job counter cannot reset the assessment budget. Each
assessment execution still allows at most one structured-output repair. Pending
generation quotas and the exact saved policy revision apply to policy-bound jobs;
legacy unbound jobs retain their existing lifecycle. Worker-side current evidence,
model approval and publication fences remain authoritative.

Before clearing the current failure, the same transaction appends a bounded
receipt to the job step: requested time, actor ID, prior state/error code,
assessment attempt count and previous finish time. No raw provider output or
credentials are copied. Receipts remain visible with the saved current brief
after a successful retry. This is retained manual-retry history, not a separate
complete audit of every automatic transport/model attempt. Obsolete input results
are still withheld by the saved reader, and there is no automatic retry on reads.

## Saved briefs in web and email digests — 8 September 2026

Digest preparation still selects deterministic source events independently of AI.
The bounded web preview and final delivery project existing assessments only:
same organization, current complete inputs, effective prompts/configuration,
observed local runtime, reviewed task/language scope and validated source citations.
They never count tokens, generate, translate, retry, enqueue or wait for a pending
brief. Runtime metadata comes from the operation's existing bounded observation,
not one probe per event. The ordinary feed and digest retain the same assessment ID.

The web preview follows the requesting user's selected locale; email reloads the
recipient's persisted locale at send time, after preparation and while checking
membership. No organization-language override or fallback to another saved
language is allowed. Missing, pending, failed, stale or unverifiable results have
an explicit state and no AI importance/prose. They do not become Low. Existing
deterministic severity/source/personal selection rules are unchanged: organization
AI importance is displayed separately from legal-impact severity.

A compact projection contains what happened, organization importance, up to
three relevance reasons with saved interest names, the suggested review/no-action
step, uncertainty, input limitations and exact saved-evidence links. If more
reasons exist, both email and web explicitly link to the full event/brief; the
original complete assessment is untouched. HTML and React escape all source/model
prose. Email evidence links use the configured application origin; no model URL
is accepted. The saved delivery summary retains the assessment ID, locale, saved
timestamp and delivered projection for audit. Old delivery summaries without a
brief remain readable; no retroactive generation or rewriting occurs.

These are bounded read-time and send-time snapshots, not a live guarantee after
an email has been sent. Existing digest job/recipient/quiet-hours/idempotency and
local-runtime freshness gates remain in effect. In particular, the older digest
runtime gate can still defer delivery when the local runtime is unobservable;
this change does not claim an end-to-end offline-delivery fallback. Notification
centre integration, enrichment wait policy, global fairness and independent
model/language/hardware/pilot acceptance remain open under HL-089/HL-079.
