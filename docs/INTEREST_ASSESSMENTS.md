# Shared event relevance briefs

HL-089 is **in progress**, not enabled in the UI. The 8 September 2026 change
provides the generation contract, transactional storage, measured local execution
and current-input admission, including material evidence from existing saved
legacy comparisons. Complete passage sets remain the fallback when no comparison
exists and they fit the contract. It does not yet
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

The repository is **not** a public admission API. Workers can now use
`AssessmentStore.prepare_current` and `finish_current`, backed by
`interest_admission.assemble`, rather than supplying interest lists themselves.
The raw storage primitives remain internal; an event-admission row alone is not
enough to prove inputs current. Runtime resolution, retry admission and durable
job integration remain required before automatic execution is enabled.

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

This is **not yet a user-facing baseline editor or automatic connector policy**.
No source snapshot is automatically assigned a predecessor, and no new matching
job or UI flow is enabled. An external mutation route must authorize the actor and
expose the selection revision; an operational connector policy must separately
justify any official predecessor relationship. Archived artifact bytes and legal
identity/chronology still need their independent verification. Downgrading this
migration removes its new selection/comparison tables, not the original corpus.

Still required under HL-089:

- Extend current-input admission with official facts, baseline selection UX and
  verified connector predecessor policy, complete large material/target-law planning and organizations with more
  interests than one dossier can fit.
- Durable job IDs, automatic matching trigger, quotas, priority/fairness,
  cancellation recovery, backoff/dead-letter handling and guarded reactivation of
  a previously superseded fingerprint; no caller may bypass currentness checks.
- Full per-attempt/token/runtime diagnostics and append-only feedback history.
- Exact-key freshness across feed, notification, digest, history and assistant
  readers, with honest pending/failed/not-scheduled presentation and bounded waits.
- Administrator-only prompt/fallback policy integration, actual profile approval,
  and evaluation of useful
  reasoning, grounding, output language, noise and target-hardware latency.

## Verification

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
