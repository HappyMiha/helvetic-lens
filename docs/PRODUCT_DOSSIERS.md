# Pharma and Loyer monitoring dossiers

Status: DONE for the scoped product implementation and production publication,
verified on 26 September 2026. Broader MV2 and professional pilot acceptance remain separate.

Two dedicated Apache-2.0 clients share this platform's identity, organization access,
source catalogue, topic matching, AI adapters, durable jobs, notifications and evidence
volume. Dossier lists are scoped by organization and product. Drafts stay author-private;
activated dossiers are visible to the current organization. Existing role boundaries
remain authoritative; viewers read and download, administrators edit and invite.
Native profiles remain accessible to authorized members through the full platform.

## Workflow and persistence

The five-step workflow from H26-07 is retained. Product dossier creation saves a native
profile and its wrapper in one transaction. Client retries reuse the same dossier.
Source recommendations use the actual catalogue and reject model-invented source IDs.
AI availability is independent of manual configuration. Activation keeps the native
source-pack, matching, subscription, consent and verified-email gates.

Dossier entries include original-source references, comments, relevance decisions,
files and AI refinement proposals. Entries carry authors and timestamps. File downloads
require current membership and dossier visibility; filenames never control storage paths.
Uploads are bounded to 10 MB, 50 files per dossier and 500 MB per organization. SHA-256
fingerprints accompany metadata. Files remain in the existing backed-up evidence volume;
retention preserves referenced files and account erasure includes private file inventory.
Shared records follow existing retained-work and detached-author rules.

Connecting an individual page uses the native public-network-safe fetcher, stores a real
baseline and enables its daily DocumentWatch with an actual next_auto_check_at. The normal
scheduler admits it to the durable scan queue. Repeated connection does not duplicate a
watch. This monitors a selected page, not the whole domain, and native fetching failures
remain visible. Pausing topic matching leaves separately configured shared page watches
and source collection unchanged; the client states this explicitly.

Saved relevance feedback is bounded context for a real call to the organization's selected
AI provider. Proposals retain model/provider, feedback references and captured topic
revisions. Applying one requires human selection and creates the native revision, backfill
job and dossier review record together. Stale/cross-dossier topic changes are refused.
Repeated acceptance is idempotent and a different choice cannot masquerade as the same
application. Source rights, source freshness and professional interpretation remain separate.

## Verification

- Exact API lint: `ruff check services/api deploy/release_manager.py` passed.
- New product dossier suite: eight cases covering durable retries, notes/export,
  cross-product and cross-organization reads, file ownership/integrity/CSRF, author-private
  drafts, viewer denial, actual model feedback input, reviewed native revisions, stale
  proposal rejection, native daily scheduler admission/deduplication, bounded catalogue
  recommendations, attachment retention and account erasure inventory.
- Final affected product/document-monitoring/maintenance run: 19 passed.
- Existing legal-profile, topic, account-erasure and backlog regressions: 32 passed in
  the preceding affected run. Initial failures in two new model test doubles were fixed;
  the final product suite passes with explicit scripted proposal responses.
- Frontend clients have strict contracts, TypeScript/lint/build gates and five gateway
  contract tests per product for cookie filtering/forwarding, route and mutation-origin
  checks, streamed upload bounds, private binary responses and visible upstream failure.
- The normal production release also passed 755 tests (96 smoke, 659 functional),
  exact API lint, backup, migration/startup and public health verification. Its separately
  configured integration suite was skipped by the existing release policy.
- No test client records were seeded into the production database. Authenticated
  workflow/privacy evidence comes from the native tests; production checks below use
  anonymous HTTP requests. Browser interaction and professional usefulness acceptance
  are not claimed by this release record.

## Deployment contract

Client repositories: HappyMiha/helveticlens-pharma and HappyMiha/helveticlens-loyer.
Production hosts: pharma.helveticlens.ch and loyer.helveticlens.ch. The original
helveticlens.ch deployment remains the shared core. No retired Monitoring deployment
is recreated, and existing private data, credentials and source approvals are preserved.
The owner explicitly authorized these additional product sites on 26 September 2026.

## Reviewed search planning — overnight development, 27 September

An administrator can submit a question to `POST /api/products/{product}/discover/plan`.
Only the entered question (5–300 characters) and the product name reach the configured
model. No private dossier context is fetched, no source request is issued and no record
is mutated. The strict response admits 1–5 source-specific queries with a label/reason
and up to four bounded scope clarifications. Provider IDs are limited to workspace,
Fedlex and Europe PMC; the prompt reflects workspace word/phrase matching, Fedlex title
substring matching and biomedical literature terms. Unknown fields/providers, fabricated
result fields and invalid limits cause a visible 502 without a partial plan.

Both clients display the original question and model attribution. Selecting a suggestion
prepares the editable search field and provider; the user separately presses Search.
The UI explains which text reaches the model or public source. Plans are transient in
the current search view; saved sources and monitoring still use their explicit flows.
Read-only users retain manual discovery. Model errors do not disable it. The endpoint
shares the existing authenticated six-per-minute AI/discovery budget across products,
requires CSRF and administrator role, and returns private/no-store responses.

Initial validation: 35 affected native product/backlog tests passed, covering explicit
model input, private-context exclusion, no hidden search/mutation, strict output rejection,
roles/session/CSRF and unavailable-model recovery alongside existing product workflows.
Each client passed seven gateway contracts, strict lint/TypeScript and a production
build; both development routes compiled and returned 200. The owner requested hourly
main pushes with product Sites deployment near 09:00 Zurich; these client changes are
awaiting that final deployment window, not claimed as published by this section. A follow-up
cross-product shared-rate-budget regression and backlog gate also passed (36 unique
affected cases across both runs).

## Initial publication — 26 September 2026

| Product | Public Apache-2.0 repository | Production | Validated source |
|---|---|---|---|
| Pharma | [helveticlens-pharma](https://github.com/HappyMiha/helveticlens-pharma) | [pharma.helveticlens.ch](https://pharma.helveticlens.ch) | `36c778deab0b71a4f52654462f1bcedc0bd8ddf2` |
| Loyer | [helveticlens-loyer](https://github.com/HappyMiha/helveticlens-loyer) | [loyer.helveticlens.ch](https://loyer.helveticlens.ch) | `74f2d7b464cd86ab1fa3c33e52ade15e49a9be8e` |

The shared core deployed `a34269fc87b14873bd25ffc9341c00fa3bb427d6`
(`git-a34269fc87b1`) at 20:37:29 UTC on 26 September 2026. Both independent
client builds passed local tests, lint, TypeScript and production builds. Their
[Pharma CI](https://github.com/HappyMiha/helveticlens-pharma/actions/runs/36270220064)
and [Loyer CI](https://github.com/HappyMiha/helveticlens-loyer/actions/runs/36270225118)
also completed successfully. GitHub reports both repositories PUBLIC and Apache-2.0.

Both Sites deployments succeeded. Custom hostnames and SSL certificates report active.
On each requested HTTPS hostname, the product page returned 200 with its correct title;
four linked CSS/JavaScript assets returned 200; `/api/auth/session` returned 200 and an
unauthenticated identity; its own private dossier route returned 401 and `private,
no-store`; the other product's route returned 404; a cross-origin login mutation was
refused with 403 by the product gateway before reaching the core. CNAME and validation
records were added only for the two requested subdomains; the apex and mail DNS were
not changed.

Operational boundaries: the clients currently use English, share the existing organization
and personal email digest, and require sign-in for private work. Source page watches are
individual URLs rather than whole-domain coverage. Source availability and configured
AI/email providers keep their native readiness gates. Saved AI improvements require
review and explicit acceptance before changing topic revisions.


## Collective research iteration — 27 September 2026 (DONE, scoped release)

The owner asked to develop both products around professional forums, with monitoring
and information discovery as the primary job. The delivered model is a private living
topic: a shared research goal, focused questions, source-linked contributions,
human-accepted working answers and continuing monitoring. Operational work supports
that loop. The existing public clients and private organizations retain their boundaries.

The new primary Topics screen shows collective activity and open questions. Workspace
search is visibility-filtered; external discovery sends only the explicitly submitted
query to fixed Fedlex or Europe PMC endpoints. Fedlex is title-based official catalogue
search; Europe PMC returns literature records. The live neutral-query checks returned
20 and 19 records respectively. Up to 20 records are exposed, with honest empty/error
states and no universal web-coverage claim. Results can seed monitoring or be saved to
a topic; individual page watching remains an explicit native operation.

Questions and replies have durable request keys, conflict detection and human acceptance
with reopening. The native configured model receives at most 18 bounded topic snapshots
(team text, saved nonsynthetic page extracts and admitted event metadata). Every finding
requires a known source ID and a quote present in the exact saved input. Invalid
citations and results produced while the topic/evidence changes are rejected. Notes
retain source snapshots, hashes, model/provider, unknowns and suggested searches. Exact
quotes prove attribution, not professional correctness. Files are not parsed for AI.

Accepted answers keep their acceptance/review time. New saved contributions, watched-page
versions or admitted matching events prompt human review without automatically changing
the accepted answer. A contributor can reconfirm after reviewing, select another answer
or reopen the question. Open gaps can enter the existing reviewed monitoring refinement.

Product context adds medicine/programme/markets/lifecycle for Pharma and
client/matter/jurisdiction/practice for Loyer. Actions have current-member assignment,
priority, team deadlines, current match fingerprints and immutable source pointers,
revision guards and required completion outcomes. Review dates and decisions persist.
The work queue has real counts, team/personal filters and pagination. Private printable
briefs include accepted answers, quoted evidence, unresolved gaps, new-material review
signals, actions and references; JSON exports retain the structured history.

Schema f4c495bef124 adds product context, actions and research threads. The migration
was tested on populated dossiers: notes and file bytes survive downgrade/upgrade, FK
enforcement remains active, and deleting an author detaches identity/assignment while
retaining shared answers. No private content or credentials enter the public repositories.

Final local verification: exact API lint passed; 51 affected product/legal-profile/
erasure/migration regressions passed. After the acceptance-time refinements, the final
product research/operations/dossier/backlog run passed all 24 cases (23 integration and
one smoke). This includes new watched-page material prompting answer review. Both
product clients passed six gateway tests, lint, TypeScript and production builds.
Native tests use deterministic model/HTTP doubles; live provider discovery uses neutral
public phrases. No authenticated production records or browser-interaction acceptance
are claimed. Product strategies and proposed pilot measures are in each client's PRODUCT.md.

Separate future gates: public communities, contributor-specific permissions, per-question
email subscriptions, semantic retrieval evaluation and more source providers. Existing
medical/legal professional validation and broader MV2 acceptance gates remain open.

### Confirmed collective research publication

The shared core activated `9137dcf2fd755d03150e1bc71f86325c452bb7ac`
(`git-9137dcf2fd75`) at 22:20:05 UTC on 26 September (27 September in Zurich).
The automatic release passed 755 tests (96 smoke, 659 functional), API lint, backup,
startup/migration and public readiness. The configured integration gate remains separate;
the 24 final affected cases were run locally before publication.

| Product | Published source | Sites version | CI |
|---|---|---|---|
| [Pharma](https://pharma.helveticlens.ch) | `0c6e331b37f13dc98104ede839951e7726ccea16` | 2 | [Passed](https://github.com/HappyMiha/helveticlens-pharma/actions/runs/36275693671) |
| [Loyer](https://loyer.helveticlens.ch) | `530261a872651aa901550de6c9c6f18055159181` | 2 | [Passed](https://github.com/HappyMiha/helveticlens-loyer/actions/runs/36275694674) |

Both saved archives came from the exact validated/pushed source; both Sites deployments
succeeded and retain public access at their existing custom production URLs. GitHub
confirms both repositories PUBLIC with Apache-2.0. Twenty-seven HTTP checks per product
passed: product title, every directly linked asset byte-for-byte against the validated
build, anonymous session, private dossiers/queue/discovery/discussion/brief denial,
cross-product discovery/queue denial and cross-origin mutation denial. The core public
readiness endpoint identifies the expected release. No DNS or source approvals changed.

This completes this scoped product iteration. It does not claim universal web indexing,
browser interaction testing, or professional pilot acceptance.


## Workspace retrieval — overnight development, 27 September

Workspace discovery now accepts `mode=all` (default) or `mode=phrase`. All-words mode
requires every distinct whitespace-separated word somewhere in the same visible record,
across its title/name, body/goal or dossier subject; word order need not match. Exact phrase
requires the full entered phrase in one field. Up to 12 distinct words are admitted;
longer queries can use phrase mode. SQL wildcard characters remain literal, and trimmed
queries must contain at least two characters.

Each group ranks contiguous title matches, then all-word title matches, then recency and
a stable ID tie-breaker. Visibility filtering precedes retrieval and counts. The response
adds actual workspace `total` and `match_mode`, preserving existing result fields and the
20-per-group limit. Public providers retain their own query syntax; their total remains
unknown rather than fabricated. Both clients expose the match choice, explain it before
searching, label the mode on returned results and show visible-versus-total counts with
refinement guidance when a group is capped. There is no semantic or whole-workspace
indexing claim and no added storage, source approval or schema migration.

Validation: all 39 affected native product/backlog cases passed (38 integration, one
smoke), including multi-field/reordered retrieval, phrase restriction, title relevance,
literal wildcards, bounded terms, accurate capped totals, stable ordering and private
visibility of counts. Seven gateway tests per client, lint, types and production builds
passed; both local routes compiled and returned 200. An accessibility lint failure on a
status paragraph was fixed by using the semantic output element before the final checks.
Client publication remains pending the final overnight window.

## Accountable research follow-up — overnight development, 27 September

A professional can create an ordinary assigned action from a question or from one
specific gap in a saved AI research note. The client opens an editable draft; nothing
is created until the person saves it. The existing administrator/member assignment,
deadline, revision and required completion-outcome rules remain authoritative.

The optional `research_origin` on action creation contains only a thread ID and, for a
gap, a saved note ID plus a zero-based gap index. The server resolves the visible parent,
requires the thread to belong to that dossier and the note to be a research entry in
that exact thread, validates the gap, and captures the question title and exact saved gap
in immutable evidence JSON with a timestamp. Browser-supplied snapshot text is rejected.
A monitoring-match origin and a research origin cannot be combined in one action. No
schema migration, source request, model call or notification subscription is introduced.

Question-filtered action reads validate thread ownership before returning their real
total and a stable 50-record page. Both clients show these follow-ups beside the question,
including responsibility, deadline, status and recorded outcome. Actions in the shared
queue and action detail link back to their research question; the printable topic brief
and JSON export retain the origin. Brief text is escaped. Ordinary action updates cannot
replace the origin, and completing a follow-up does not accept or close a working answer.

Action idempotency retains the exact pre-feature fingerprint when no research origin
is provided, including explicit null. Existing published clients can safely retry their
previously created actions throughout the overnight backend deployment. A changed origin
under the same request key is a conflict. Viewers can read visible shared follow-up, while
CSRF, organization, product and private-draft boundaries still guard reads and writes.

Validation: 44 affected native product/backlog cases passed (43 integration, one smoke)
and exact API lint passed. Five new cases cover exact saved origins and retained outcomes,
no automatic answer acceptance, wrong question/note/dossier/gap rejection, private roles
and organizations, real 55-action filtered pagination, escaped briefs and legacy action
retry fingerprints. Both clients passed seven gateway tests, lint, TypeScript and builds.
This background heartbeat did not run browser interaction QA; client production deployment
remains reserved for the final overnight window. The previous search core release
`git-914695a40c9c` was verified active at 01:15 Zurich on 27 September.

## Connected-page health and recovery — overnight development, 27 September

Both product clients distinguish the last native check attempt, last successful accepted
nonsynthetic check, saved version time and next automatic check. A failed attempt keeps
the previous successful-check timestamp and saved evidence. Saved content can be older
than a successful unchanged check, so these dates are deliberately separate. The new
nullable `DocumentWatch.last_success_at` uses migration `f5c495bef124`; only a known
successful latest attempt with an accepted nonsynthetic current version is backfilled.
Historical failures, reused baselines and unknown times remain unknown.

Connected references are deduplicated by native document. The private dossier payload
exposes its organization watch's failure diagnostic, pending scan state and schedule:
paused, manual, missing administrator, unscheduled, due or scheduled. A successful check
older than 48 hours is labelled for review. This age threshold describes one page check;
it does not measure whole-topic coverage or certify the source's current correctness.
Synthetic versions and missing success history remain visibly distinct from live checks.

The clients reuse native commands to retry/check, refresh status, pause/resume a watch,
and toggle daily checks. Queued or paused watches cannot admit another check from the
card. Settings apply to the organization document wherever reused, with explanatory
copy distinguishing them from topic matching. There is no new source, scheduler,
automatic browser refresh, AI request or notification channel. Existing native role,
organization, CSRF, operator eligibility and duplicate-admission guards remain in force.

Validation: exact API lint and all 59 affected native cases passed (58 integration, one
smoke), including real failure/recovery, synthetic handling, conservative populated
migration with intact foreign keys, deduplication, queue/schedule states and private
diagnostics/settings. Each client passed seven gateway and three status-semantic tests,
lint, TypeScript and production build. The previous follow-up core `git-d558b4cabe5c`
was verified active at 01:35 Zurich. Final client publication remains reserved for
08:00–09:00; this background heartbeat did not perform browser interaction QA.

## Shared saved searches — overnight development, 27 September

Teams can keep a useful search with its dossier: exact trimmed query, supported provider,
workspace match mode and optional purpose. The server records the author and save time
in an ordinary private `saved_search` entry. Saving is a recipe operation, not proof of
executing that query, a copy of search results or a scheduled search. The input contract
rejects execution/result/schedule claims, unsupported providers and incompatible modes.
All-words workspace recipes retain the 12-distinct-word limit; exact phrase and public
provider syntax keep their existing behavior.

The saved-search view has accurate totals and stable 50-record pages with loading/error
recovery. In both clients, Review search opens the existing editable discovery form with
its provider and mode selected. Opening it does not make a source request; pressing
Search remains explicit. Save search uses the displayed result's query, even when the
unsubmitted input has since changed, and excludes result records and retrieval timestamps.
Failed saves retain the visible result, purpose and same request key for retry.

The new `/dossiers/{identifier}/searches` GET/POST routes reuse private parent visibility,
organization locking, administrator write access, viewer reads and CSRF. Reusing a request
key with a changed query, mode or purpose is a conflict; collisions with other entry kinds
cannot overwrite them. JSON export retains the recipes within the existing export limit,
and the printable brief includes the latest 50 with escaped queries and purpose text.
Saved queries are excluded from research evidence and do not alone mark an accepted
working answer for review. There is no migration, additional provider, AI call, source
fetch, subscription or monitoring activation on save/read.

Validation: 54 unique affected native cases passed across the regression run and one
corrected test-helper rerun (53 integration, one smoke); exact API lint passed. Five
new cases cover persistence, validation and key conflicts, 55-record pagination,
organization/product/draft/role/CSRF boundaries, safe brief/export and separation from
AI evidence and answer-review signals. Both clients passed twelve tests, lint, strict
TypeScript and their production build. Sites 0.1.70 execution-profile configuration
preserved the existing custom checkouts; its build helper ran the existing build script.
No browser handoff/interaction QA was performed in this background run. Both client
deployments remain intentionally reserved for the final overnight publication window.

## Public result continuation — overnight development, 27 September

Explicit discovery can continue in 20-record pages, up to 1,000 provider records per
interactive search. The shared API preserves its original first-page response fields
and adds continuation/page/omission metadata. Europe PMC's cursor and source-reported
hit count are used when supplied; an unknown total remains null. An exhausted known
total, missing cursor, empty page or repeated cursor cannot create an infinite next-page
loop. If the reported total suggests more results but continuation is missing, the
client explains that limit instead of treating it as complete coverage.

Fedlex title discovery groups records by legal-work URI, chooses one matching title,
orders by URI and requests one extra work to determine whether another page exists.
No full count is inferred. Exact query literals remain escaped, and source identifiers
retain existing URL validation. Dropped invalid or duplicate provider rows are counted.
The native response byte/timeout limits and shared discovery rate budget remain intact.

Continuation values contain only bounded public pagination state: provider, query hash,
page offset and the provider cursor. They confer no authority and are validated as
untrusted input; they cannot specify a host, arbitrary URL or private context. Changing
the query/provider, using a workspace cursor, malformed data or exceeding the interactive
limit is rejected before any provider request. The client's next-page request uses the
displayed result's query rather than any newly typed, unsubmitted query. Earlier visited
pages remain in this open view; a failed request preserves them and the current result.
A new explicit Search resets the page sequence only after a successful response.

This follows the [Europe PMC REST contract](https://europepmc.org/RestfulWebService),
its [cursor/end-of-results announcement](https://groups.google.com/a/ebi.ac.uk/g/epmc-webservices/c/yG8kMl1R3cI),
the [official Fedlex-JOLux query examples](https://swiss.github.io/fedlex-jolux/introduction.html)
and [SPARQL 1.1 solution modifiers](https://www.w3.org/TR/sparql11-query/#solutionModifiers).
These are live catalogue pages, not reproducible search receipts, comprehensive web
indexing or standing query monitors. Saved search recipes still exclude result records,
retrieval times and continuation state. No new source, model call, storage or schedule
is introduced.

Validation: all 64 affected native cases passed (63 integration, one smoke), followed
by eleven focused source cases after the final known-total exhaustion guard; exact API
lint passed. Both clients passed fourteen tests, lint, TypeScript and production builds.
The existing discovery rate budget remains six requests per minute in its shared bucket.
A bounded read-only live probe traversed two Fedlex pages for `Datenschutz` (20/20 works)
and two Europe PMC pages for `GLP-1 safety` (19/20 usable records; one first-page record
omitted). Neither traversal overlapped across pages. Europe PMC supplied a live count
of 34,662; no Fedlex total was inferred. These counts are probe-time observations, not
fixed product claims. Final Sites publication remains pending the end-of-night window;
this background run performed no browser interaction QA.


## Imported source provenance — overnight development, 27 September

Explicitly importing a public Discovery hit now preserves its exact query, provider,
page, retrieval time and normalized catalogue record. `product_provenance.py` signs
these bounded values using the native actor/session-scoped HMAC pattern with a distinct
format and a 30-minute lifetime. The current user, workspace, login and product are
bound into verification. The receipt grants no access and never supplies an arbitrary
network target. Membership and session validity are reread after the awaited public
search; imports recheck current administrator membership and session under the native
workspace/account locks and enforce ordinary dossier visibility.

`POST /api/products/{product}/dossiers/{id}/discovery-references` accepts only a UUID
request key and receipt. It performs no source or model request. An authorized exact
retry returns the same entry; a completed import can be retried after expiry in the
same valid session. A new expired import, changed body, reused key with a different
receipt, wrong actor/session/workspace/product or invisible parent fails without a write.
The saved ordinary reference contains the validated origin and a receipt hash; the
receipt and signature are not persisted. Existing manual references remain supported
and do not acquire a provenance claim. No database migration is needed.

Both clients send only the receipt, retain a request key per receipt for lost-response
recovery, and prompt a fresh search if it is missing or expired. Evidence & sources
shows the original query, catalogue record and retrieval time. The escaped brief and
JSON export retain that origin; full catalogue titles remain available when the entry
title needs the existing 240-character limit. This proves the application's recorded
search/import path, not source correctness, full-text capture, current legal/medical
validity, completeness or active monitoring. Connecting a page watch remains explicit.
Client browser storage, automated search reruns, new providers and email behavior are
unchanged. The background run performs no browser interaction QA or premature Sites
activation; the final client release remains reserved for 08:00–09:00 Zurich.

Validation: all 82 affected native cases passed (81 integration and the backlog smoke
gate), including 18 dedicated provenance cases and a verified second-page import.
Exact API lint passed. Both clients passed 17 tests, lint, TypeScript and production
builds through the Sites helper. No browser interaction verification is claimed.


## Team source decisions — overnight development, 27 September

Saved references now expose the current team's source review. An administrator chooses
Include, Exclude or Needs review and explains why. The decision applies to an exact URL
within one dossier, including duplicate references to that same URL. Different URL
strings, dossiers, products and organizations remain independent. These are relevance
decisions, not validation of medical/legal correctness. Unreviewed remains eligible for
new AI research to preserve existing behavior; eligibility is not a promise that the
bounded relevance selection will choose that source.

`product_source_reviews.py` uses existing append-only `source_review` entries. GET/POST
`/api/products/{product}/dossiers/{id}/sources/{reference_id}/reviews` resolve a real
reference under ordinary parent access, reread current membership/session, and serialize
writes under native workspace/account locks. A required expected review ID protects
against concurrent edits, including through a duplicate reference. Per-URL monotonic
revisions determine the current decision even when timestamps do not sort the same way.
Exact retries return the original saved review without overwriting a later decision;
reusing a request key with a different body cannot overwrite an earlier entry. History has true totals
and 50-record pages. Erased authors use the existing Former member attribution.

Both clients show the current decision, author, explanation and time on source cards.
The review dialog preserves draft explanations after errors and conflicts. Refreshing
history never silently changes the draft's expected revision; the user explicitly
reviews the latest decision and chooses it as a new starting point. Retry identity is
retained for the same submission. Viewers can read history but cannot review sources.
The dialog uses existing accessible primitives and a bounded responsive scrolling area.
No browser interaction verification is claimed in this background run.

New AI research excludes saved contributions, connected-page extracts and saved event
metadata at excluded exact URLs. Review explanations themselves are not AI evidence.
The review vector is captured before inference, checked again before saving, and stored
with the saved research note; any intervening review decision rejects a stale result,
even when selected text happened to stay the same. Old accepted answers and citation
snapshots are retained, with the existing answer-review signal after a source decision.
Neither this review operation nor listing history fetches sources, calls a model,
changes topic revisions, pauses a watch or alters email behavior.

The private brief shows current decisions next to references and the latest 50 review
records with the actual total; HTML is escaped. JSON export retains current decisions
and review entries within its existing 10,000-entry limit. No new schema, external
service, provider coverage or public collaboration surface was introduced. Final Sites
activation remains reserved for 08:00–09:00 Zurich.

Validation: all 92 affected native cases passed (91 integration and the backlog smoke
gate), including ten new review cases. Exact API lint passed. Each client passed 20
tests, lint, TypeScript and final production builds. No browser interaction QA.


## Complete source library — overnight development, 27 September

The Evidence & sources tab now retrieves saved references independently of the latest
100 mixed activity entries. A long-running collective topic can accumulate notes,
actions and review history without hiding its older source references. The dedicated
private GET `/api/products/{product}/dossiers/{id}/references` provides 30-reference pages
with stable newest-first ordering and an ID tie-breaker. Duplicate references remain
separate saved records and share the existing per-URL current review.

Search uses literal case-insensitive all-word matching across reference title, notes,
URL, imported query and catalogue title/provider/identifier. All words must match
somewhere in the same reference; percent and underscore are literal, not wildcard
operators. The request is bounded to 300 characters, 12 distinct words and a nonnegative
32-bit offset. A blank query lists all saved references. Review filters use the latest
numeric review revision, with absent or reset reviews classified as Needs review.
Counts are calculated from the complete server-side reference set. `dossier_total` is
all saved references; `counts` contains current review facets within the submitted text
query; `total` additionally applies the selected review filter. Counts never derive
from just the loaded page or recent activity.

Both clients keep query/filter editing separate from the displayed search. Search and
Clear filters return to page one; Previous/Next use the displayed query and decision,
not unsubmitted edits. The library has explicit refresh/retry, initial-empty and
no-match messages, and a first-page recovery if concurrent activity empties a later
page. Failed reads hide stale library content while preserving filter inputs. Source
additions and reviews refresh server state, while provenance, review history and native
page-watch controls remain on each card. The unrelated older-activity control is no
longer shown beneath this source library; other dossier tabs retain it.

All source reads preserve session, organization, product, author-private draft and
viewer boundaries. They do not call a source provider or model, write records, start
monitoring or alter email. No migration, external service, full-text indexing or browser
storage was introduced. Native `no-store` and the client gateway's `private, no-store`
responses remain intact. This library searches saved reference metadata, not attached
files or the full external source text. Source coverage and the final Sites publication
window are unchanged.

Validation: all 98 affected native cases passed (97 integration and the backlog smoke
gate), including six source-library cases. A fixture with 125 older references and 120
newer mixed entries proves complete source retrieval and stable five-page traversal.
Current-review facets, reset behavior, literal text/catalogue lookup, both products and
access boundaries passed. Exact API lint and both clients' 22 tests, lint, TypeScript
and production builds passed. No browser interaction QA is claimed.


## Exact saved-source links — overnight development, 27 September

Workspace discovery opens a matching reference directly in Evidence & sources. The
private GET `/api/products/{product}/dossiers/{id}/references/{reference_id}` resolves
only an actual reference with a URL in the visible parent dossier. It returns existing
catalogue provenance and the latest per-URL review, independent of mixed activity,
source-library text filters or pagination. Fresh session/membership, private-draft,
organization and product checks apply on every read. Viewers can read; the endpoint
cannot create or change a record, fetch an external source or invoke the model.

Each saved source has an ordinary product-domain `?dossier=...&source=...` link. Only
identifiers appear in it; knowledge of the URL grants no access. The same route survives
reload and signing in. Source links take precedence over a conflicting question argument;
question and discussion-result links retain their question destination. User navigation
creates history entries; boot, login continuation, refresh and popstate replay do not.
A navigation sequence prevents a late dossier request from replacing a newer target.

Both clients display the exact source with its existing provenance, decision/history
and explicit page-watch controls. A failed read hides any previous record and offers
retry/return to library. The library remains accessible with its search/filter state
in the current component. Source focus is announced by focusing its heading; the library
precedes other Evidence content. No private content is copied to clipboard automatically,
shared publicly, sent to a provider or added to a notification subscription.

Verification: all 101 native product/backlog cases passed (100 integration, one smoke),
including three new exact-reference cases covering both products, 110 newer references,
provenance/current decisions, read-only behavior and no source/model side effects.
Cross-parent, non-reference, absent, product, tenant and private-draft references remain
inaccessible; authorized viewers can read. Exact API lint passed. Both clients passed
25 tests (three new navigation cases plus existing gateway/workflow coverage), lint,
TypeScript and Sites-helper production builds. Navigation tests cover ID-only escaped
links, source/question/topic destinations and replay preserving forward history. Client
lint identified synchronous effect resets; navigation now remounts dossier state on
actual transitions and clears review dialogs in user actions, without bypassing checks.
No browser interaction QA or final Sites activation is claimed.


## Reviewed AI inputs — overnight development, 27 September

Eligible saved team contributions are ranked by literal question-word matches across
title/body before the 30-record candidate limit, with date/ID tie breaks. Up to 20 distinct
question words of at least four characters participate. Blank space-only bodies are
skipped before selection; final snapshots require nonblank text. Team and page excerpts
start up to 180 characters before their first matching word and retain at most 1,800
characters. This helps old relevant text survive newer unrelated activity and preserves
exact contiguous excerpts. It is not semantic search or complete evidence coverage.
Existing latest-20 connected-page, six-topic, 20-matches-per-topic and 18-final-snapshot
bounds, current-event gates and exact-URL source exclusions remain explicit.

GET `/api/products/{product}/dossiers/{id}/discussion/{question_id}/research-preview`
returns the exact question/context/monitoring goal and selected saved snapshots, provider,
model, preparation time and limits. A deterministic fingerprint binds the organization,
product, dossier, question and revisions, exact input and current source-review vector.
Preparation time is excluded from the fingerprint, so unchanged previews remain stable.
The native private viewer/read rules apply. Reading makes no model/source request, entry,
watch or notification change, and uses the normal read budget rather than the AI budget.

Both clients now open this preview before AI generation. The dialog shows source kinds,
exact excerpts, the question/goal, original URLs and saved-reference links. It explains
selection limits and empty evidence, supports explicit refresh/retry, and hides stale
preview content after a read error. Generation is a separate administrator action; the
browser sends only expected revision, preview fingerprint and a stable request UUID.
It cannot replace server-side excerpts with edited browser text. Old clients that omit
the new optional expected_evidence field remain supported through final publication.

The server checks current session/membership before inference, recomputes the preview
identity and rejects changed inputs before calling the model. It checks current write
access again after inference, then the complete captured identity before saving. Existing
exact-quotation validation, bounded output and human answer acceptance remain intact.
Saved notes retain input_fingerprint and the supplied preview_fingerprint (null for
legacy requests). Same-author exact retries return the original note without another
model call; different preview, revision, question or author cannot reuse the key. A
fingerprint is an optimistic input check, not an authorization token or evidence that a
human certified source truth. No schema migration, new provider or file parsing.

A successful note followed by a failed topic refresh remains visibly saved in the dialog;
retry opens it without generating again. Leaving the view suppresses stale completion
callbacks, and dossier refresh checks the navigation sequence before replacing a newer
selection. Responsive dialog layout uses existing primitives and scrolls within the
viewport.

Verification: all 116 native product/backlog cases passed (115 integration, one smoke),
including fifteen new preview/retrieval cases. These cover both products, old relevant
long text behind 60 newer unrelated records and 35 blank references, stable deterministic
previews, exact model inputs and excerpt hashes, exclusions/empty evidence, legacy and
same-author retries, question/actor key conflicts, strict payload/CSRF/private/viewer
boundaries, five kinds of pre-inference input changes, and role/session revocation before
and after inference. Preview reads leave entries, source/model activity and the AI budget
unchanged. Existing exact-citation and inference-time change regressions also passed.
Exact API lint passed. Both clients passed 28 tests (two new preview request cases and
one new gateway case), lint, strict TypeScript and Sites-helper production builds.
Responsive layout, failure recovery and source-link guards were reviewed in code; no
browser interaction QA or final Sites activation is claimed. Tenth core `git-581218bf6a9b`
was verified active since 04:59:28 Zurich; final client publication remains 08:00–09:00.

## Saved source history and reader — overnight development, 27 September

Read-only product routes `/dossiers/{id}/documents/{law_id}/versions` and
`/dossiers/{id}/documents/{law_id}/versions/{version_id}` reuse native law-history
metadata and the native SQL evidence pager. They require fresh current membership,
the same visible product dossier, an actual monitor entry, the organization's
DocumentWatch, visible Law and an exact visible Version/law relation. These checks
also apply before returning the read; viewer access and author-private drafts keep
their existing meaning. No schema, source request, model inference, acknowledgement,
read milestone, saved entry, watch setting, schedule or notification is added.

History uses fixed 20-record pages with native scoped cutoff cursors, stable saved-time
and ID ordering, true accessible totals and explicit refresh. Going back retains the
original first-page cursor. The cutoff excludes newer captures; later corrections and
backdated imports can change the list. Metadata projection strips native application
routes and artifact keys/URLs and does not hydrate saved text or passage bodies.

A saved version loads at most 50 passage records or 16,000 Unicode characters, using
server offsets rather than JavaScript string lengths. The reader sends the selected
metadata's evidence_revision from the first page onward; the API checks that revision
and exact law relation before and after reading. Corrections and reassignment cannot
silently combine text from different saved revisions. Explicit first-page reload can
adopt the current revision. Unreadable passage records are counted separately without
changing the native positions or total. Empty text remains visibly empty.

Both clients open the responsive history/reader from connected page watches. They
show capture and declared-document dates, provenance, synthetic/imported status,
selected-article scope and source version date, language when available, page counts
and exact escaped text. Original-source links allow only HTTP(S). Reading is not a live
check; the original page may have changed. The advanced native history link remains.
Every resource transition mounts a fresh read and failed reads hide previous content;
retry, refresh, older/newer history, previous/next text and return-to-history controls
remain available. The reader does not expose raw original-artifact downloads.

Verification: exact API lint and all 124 native product/backlog cases passed (123
integration, one smoke). Eight new reader cases cover both products, complete 47-version
history with tied saved times, stable cutoff/backtracking, no full Version ORM loads,
111 exact passages and Unicode text reconstruction, synthetic/imported/selected-article
provenance, missing/empty/unreadable evidence, changed revisions during/between reads,
version reassignment, private drafts, removed monitor links, watch/Law/Version ownership,
wrong parent/product/tenant, viewer reads and write denial, cursor/offset bounds and no
source/model/entry side effects. The additional native history/evidence regressions also
passed (31 in the focused run, including the eight new cases; 23 additional unique cases).
Both clients passed 32 tests (three history/text navigation cases and a private gateway
case added), lint, strict TypeScript and Sites-helper production builds. No browser
interaction QA or final product Sites activation is claimed.

## Open the saved document behind research — overnight development, 27 September

New saved_page_extract candidates retain document_id and evidence_revision with their
exact text, hash and source identity. These fields participate in the existing preview
and inference fingerprint, so even a corrected passage extraction with unchanged
excerpt text requires a fresh preview. Candidates now require the current organization's
DocumentWatch and a visible Law in addition to a visible nonsynthetic Version. Losing
that access removes the candidate and invalidates an earlier preview before inference.
The existing post-inference fingerprint check also rejects a changed saved revision.

GET `/dossiers/{id}/discussion/{thread_id}/research/{entry_id}/sources/{source_id}/document`
resolves a saved note's exact source. Current session/membership and visible private
parent are required; the stored entry must be research belonging to the same question
and dossier. Only its actual saved_page_extract source can resolve a visible Version,
and the native dossier-monitor/watch/Law relationship is checked again. Browser-supplied
source metadata cannot replace the target. A recorded original document ID cannot follow
a version reassigned elsewhere, and malformed recorded revisions fail closed.

The locator returns only the document/version identities and recorded revision status.
It does not fetch text, invoke the model, write a record, alter the note or change a watch.
New sources open their captured evidence revision using the existing bounded reader;
corrections require explicit first-page reload. Older notes lacking both new fields
return an explicit unrecorded-revision status and open only a currently accessible saved
version. They are not backfilled or treated as verified matches to a historic revision.
Original excerpt text, findings, hashes and exports remain unchanged.

Both clients offer Read saved document beside page citations, retained page-source
snapshots and page excerpts in the AI preview. The reader keeps the exact research
excerpt available for comparison and explains when the legacy revision is unknown.
Preview wording makes clear that opening a source does not generate a research note.
The full reader starts at the first page; automatic quote location is not claimed.
Failed lookups retain an explicit retry, and a request sequence suppresses a late reader
opening after navigation. Existing reader ownership/revision guards apply to every page.
No schema migration, provider, public sharing, notification or external request is added.

Verification: exact API lint and all 136 product/backlog cases passed (135 integration,
one smoke), including twelve new citation-reader cases. They cover both products,
recorded source identity/revision through inference and export, unchanged historical
snapshots after correction, explicit legacy resolution without backfill, private drafts,
wrong source/kind/note/question/parent/product/tenant and viewer boundaries, malformed
revision rejection, reassignment, removed monitor/watch/Law/Version access, no locator
source/model/entry side effects, and stale previews before or during inference even when
the excerpt text/hash stays identical. Existing saved-reader and research regressions
also passed. Both clients passed 36 tests (three source-target contracts and one private
locator gateway case added), lint, strict TypeScript and Sites-helper production builds.
No browser interaction QA or final product Sites activation is claimed.

## Human review after saved-evidence changes — overnight development, 27 September

An accepted AI answer now has explicit review reasons when one of its saved-page
snapshots changes revision, loses current dossier/monitor/watch/Law/Version access or
becomes accessible again after an acknowledged absence. Only scalar source metadata is
read; no full Version body, source request or model call is required. Original AI text,
quotes, hashes and captured source identities stay unchanged. Existing newer-contribution,
source-decision, new-page and current-match signals remain, with separate reason codes.

Each explicit acceptance/reconfirmation stores `answer_evidence` schema 1 and the current
saved-page states in the existing attributed private review audit. The newest matching
acceptance audit is selected by question revision, scoped to parent/question/accepted
entry. No migration is required. Ordinary contribution acceptance has no AI page snapshot
baseline. Reopening clears the accepted answer and its current warning state, without
removing the note or historical reviews. Audit export retains the acknowledged metadata.

The warning compares current states against the last human acknowledgement. Acknowledging
missing evidence records that known limitation; it does not restore access or update the
AI note. A later correction, disappearance or restoration requires another review. Older
acceptances without the new baseline compare the note's captured revisions where known;
an unrecorded original revision needs one explicit review. Reading or refreshing cannot
acknowledge evidence or silently change the accepted answer.

Private question reads return `answer_review` with reasons, affected source IDs, last
review time and a deterministic fingerprint. Its identity includes workspace, product,
dossier, question/revision, accepted entry/time, current page states and prior baseline,
plus counts and latest-time/ID watermarks for newer material. Reconfirmation can provide
optional `expected_review`; current admin/session checks, question revision and the
review fingerprint must still match before the audit is recorded. A stale request
returns 409 without updating acceptance. Old clients omitting the optional field retain
explicit legacy acceptance/reconfirmation behavior.

Both clients show the specific reasons and source IDs beside the working answer, keep
the exact-source reader available in the note, and provide Refresh review and explicit
Reconfirm after review. Their request includes only question revision, accepted entry ID
and the displayed fingerprint; missing/malformed state cannot downgrade to an unchecked
request. Failed/conflicting requests retain the warning and a refresh route. The private
printable brief uses the same escaped reason messages. These signals concern saved
material and current access, not comprehensive external change detection or source truth.

Verification: exact API lint and all 147 product/backlog tests passed (146 integration,
one smoke). Eleven new answer-review cases cover both products, corrections without a
new capture timestamp, zero read/model/source/entry side effects and no full Version ORM
loads, specific brief reasons, attributed exported acknowledgement states, unchanged
historical AI snapshots, repeated corrections, Law/Version/watch/monitor access loss and
restoration, reassignment and reopening, legacy acceptance/source revisions, stale source
and new-material fingerprints, duplicate stale confirmation, CSRF/viewer/private-draft/
product/tenant denial and unauthenticated reads. Existing newer-material and reconfirmation
regressions passed; the brief expectation now names the precise new-page reason. Each
client passed 39 tests (two reviewed-request cases and one gateway conflict case added),
lint, strict TypeScript and final Sites-helper production builds. No browser interaction
QA or final product Sites activation is claimed.

## Private question retrieval — overnight development, 27 September

The existing `GET /products/{product}/dossiers/{id}/discussion` supports optional `q`
with up to 300 characters and 12 distinct words. All words must match the title or
question context, with escaped literal wildcard characters. Title matches rank before
updated time and ID; requests without terms retain the prior ordering. Existing
all/open/answered filters and 30-record pages remain. The response adds `dossier_total`,
matching `counts`, displayed `query`, `status`, `offset` and `page_size` beside the
compatible `items` and `total`. Replies, attachments and external pages are outside this
search. Fresh session/membership and the existing product, tenant and private-draft
parent checks apply on every read. No stored data, model call or source request changes.

Both clients provide explicit search, clear/reset, answer-status counts, refresh/retry,
correct empty/no-match/out-of-page states and first-page recovery. Paging uses the
returned query/filter, so unfinished form edits cannot change its meaning. List read
failures hide retained results. A failed exact-question read retries its original ID and
reply page or returns to the list. Cancelled and superseded question reads and errors
cannot replace the current view. Product-specific example terms retain the two verticals.

Verification: exact API lint and all 152 product/backlog cases passed (151 integration,
one smoke), including five new cases for complete tied-date pagination behind newer
activity, literal and cross-field matching, title relevance, query-only scope, both
products, changing answer facets, validation limits, private/viewer/revoked-member reads,
write denial and no read side effects. Each client passed 44 checks, authored-source lint,
strict TypeScript and Sites-helper production builds. Four new client contracts cover
query/page identities and delayed-read recovery; one gateway case retains literal search,
filters/pages and private validation failures. Browser interaction QA and final product
Sites activation remain unclaimed until separately verified.

## Product guide and 1.2.0 preparation — 27 September

Each client now has a public `/guide` with its own product title, canonical URL, domain,
example goal and medicine/programme or client/matter vocabulary. A persistent sidebar
link opens help in another tab so the working view is retained. The eight-part guide
explains the current ask/discover/monitor/collaborate/research/review/action loop and
six recovery cases. It documents actual coverage, current roles and private drafts,
local unsent question/reply text, saved monitoring drafts, catalogue provenance, source
review decisions, bounded AI input review, saved-evidence revision reading, explicit
answer acknowledgement and personal organisation digest scope. No application data or
new source, provider, model, authentication or notification behavior is introduced.

Both public repositories include a 1.2.0 change record and guide links; the package
version is 1.2.0 with unchanged dependencies/lockfiles and Apache attribution. The change
record explicitly separates validated/pushed source from later production activation.
All 44 client contracts, authored lint, strict TypeScript and Sites-helper builds passed
in each client. Local read-only HTTP verified 200 responses, exact guide titles/canonical
URLs and all eight sections. The shared API source remains the validated 152-case
baseline; only its release documentation changes in this slice. No new low-value tests
were added for static guide copy and no browser interaction or visual QA is claimed.

Public Sites audience, current version 2 and the original project IDs were verified
before the final window. A private final verification script requires exact expected
source SHAs and core release, checks guide/root HTTP responses, compares served asset
hashes with the validated builds and exercises anonymous private-route and gateway
boundaries without an authenticated session, external search or model call. Its live
receipt is pending final production publication in the 08:00–09:00 Zurich window.
