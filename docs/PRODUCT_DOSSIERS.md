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
