# BaselTech and Ukraine pilot verification — 21 September 2026

This records operator preparation of demonstration workspaces with real public
sources. It is not independent pilot feedback or evidence of legal completeness.
Accounts, credentials and private workspace records are not repository artifacts.

## Source recovery

The production symptoms were reproduced against the official services:

- Basel-Stadt dataset 100354 contains a null `version_url_de` and null text for
  version 262305. A valid catalogue page previously failed as a whole. The adapter
  now retains the exact OGD version lookup and explicitly unavailable publisher
  link as metadata-only evidence, while ingesting adjacent valid documents.
  No publisher URL, text or legal effective date is invented.
- Fedlex ELI manifestation URIs redirect to the Casemates metadata application.
  The connector now follows the actual `jolux:isExemplifiedBy` file from the
  official SPARQL response. Both its URL and the final response must belong to the
  same manifestation's filestore prefix. The ELI URI remains in provenance.
- Consultation artifacts used an OPTIONAL join across independent draft,
  attachment and impact properties. That multiplied repeated facts until the
  normal extraction limit rejected the result. Independent UNION fact rows keep
  source task identity and all returned values without that product. Existing
  byte, text and passage limits remain unchanged.

Read-only live probes of the corrected adapters:

| Source sample | Observed result |
| --- | --- |
| Basel-Stadt newest catalogue page | 20 references, including one explicit missing publisher link |
| Fedlex `eli/oc/2026/483` | DE/FR/IT exact official files readable; respectively 272/277/278 extracted characters |
| Fedlex `eli/dl/proj/2021/126/cons_1` | DE/FR/IT source JSON readable; respectively 5,673/5,425/5,755 characters and 187 passages each |

The Fedlex sample concerns a published EDI premium-region amendment. The text's
stated future commencement is preserved and is not confused with retrieval time.
Full original files are retained by normal ingestion. Basel annex coverage remains
excluded by the existing source contract.

Final regression run: 41 tests passed across Basel-Stadt, Fedlex, broad official
connectors, the shared connector runner and the backlog integrity gate. Checks
include rejected foreign files, wrong-language files and redirected evidence, as
well as metadata-only replay. Exact API Ruff gate passed. No frontend code changes
are part of this source-recovery change.

Commands: `services/api/.venv/bin/ruff check services/api deploy/release_manager.py`
and `services/api/.venv/bin/pytest services/api/tests/test_basel_stadt.py services/api/tests/test_fedlex_connector.py services/api/tests/test_broad_official_connectors.py services/api/tests/test_connectors.py services/api/tests/test_monitoring_progress.py::test_actual_backlog_has_complete_unique_sections_and_preserves_customs_deferral -q`.

## Live readiness boundaries

The existing platform diagnostics expose all nine native monitor sections. At the
initial inspection, warnings had a current permitted source; river and air had
public source contracts but old acquisitions. Public SIMAP publications were
configured. Pollen permission, transport credentials/permissions, FEDRO access,
auction source permission and IPI monitoring permission were unavailable.
Configuration presence is not proof of coverage; these gaps must not be hidden or
filled with invented observations.

The two requested Basel accounts share one organization with administrator/viewer
roles. The Ukraine account has a separate personal workspace. Demo setup must use
normal authenticated APIs, explicit subscriptions and real saved official source
material. New demo identities have no platform-wide administrator privileges.

Publication, production activation, scenario testing and independent human
acceptance are separate gates. Broader MV2-052 and MV2-058 acceptance stays open.

## Direct cantonal law monitoring

The pilot exposed a second acquisition problem: stable Basel-Stadt and Bern law
links serve JavaScript shells. The bounded native resolver now reads the official
publisher's current-version metadata, verifies the systematic number, language
and selected version, then downloads that exact official PDF. Stable links follow
the publisher's current selection on each scan; explicit historical-version
links remain pinned. Metadata URL/hash and selected version are retained in
provenance. Annexes are included only when the selected publisher metadata
explicitly supplies an annex-inclusive PDF. No catalogue-wide Bern coverage is
claimed, and existing download/extraction limits and source boundaries remain.

Live read-only probes retrieved Basel-Stadt 153.260 version 6649 (22 PDF pages),
Bern 124.1 version 2114 (11 pages), and Bern 122.20 version 3417 (17 pages).
Explicit historical resolution of Bern 124.1/2114 returned the same source PDF.

The focused extraction, resolver and backlog tests passed: 52 tests. They verify
that the same stable URL produces a real text difference when the publisher
changes its selected version, historical selection is preserved, and mismatched
law/version/language, foreign URLs, redirects and non-PDF responses fail closed.
The exact API Ruff gate passed. Production activation is a separate pending gate.

## SEM FAQ completeness

A real baseline acquisition exposed silent partial extraction: the SEM Ukraine
FAQ yielded only 118 characters from the first embedded article. Its explicit
`#content.main-content` contains the complete FAQ and sibling articles. Extraction
and discovery now prefer explicit main roots over article fragments and retain
collapsed answers. The HTML extractor revision is recorded as `native-html-v4`.
On the same downloaded official HTML, this yields 52,815 characters across 301
passages. This is a parser correction, not a change in migration law. The pilot
baseline must be re-acquired after activation rather than presented as an actual
legal amendment. All 60 focused extraction, LexWork, evidence-page and backlog
tests passed, including sibling-answer changes and navigation exclusion; the
exact API Ruff gate passed.

## Requested Fedlex edition

The German DSG watch initially reused an existing Italian artifact because direct
document deduplication ignored language. New direct-watch identities include the
requested language and any explicit version date. Legacy records are reused only
when their URL resolves to that same edition; their IDs, watches and evidence are
preserved. The native regulatory corpus still uses the multilingual ELI work.
Eleven focused requested-edition, authentication, synchronization and backlog
checks passed, including alias duplicates and preservation of a legacy Italian
record. The exact API Ruff gate passed. The pilot DSG watch awaits correction
through the normal document API after activation.

The ORM official-host list now also recognizes `www.fedlex.admin.ch`. Direct-watch
lookup may reuse a requesting tenant's own legacy private edition while retaining
its privacy; an existing watch takes precedence over shared aliases. Twelve
requested-edition/authentication/synchronization/backlog tests and exact API Ruff
passed. This also prevents repeated `www` adds from reaching a private uniqueness
error after an incorrectly scoped shared lookup.

## Local AI runtime and bounded planning

The running local runtime is Apertus 8B Q4_K_M with a measured 4,096-token context;
new workspace defaults referenced the inactive 1.5B model. Only the two pilot
workspaces were configured to use the running model, a 4,000-character evidence
budget and 900 completion tokens. The Basel AIG comparison then completed as
`selected_evidence`: exact cited passages, explicitly **no generated impact
assessment**. Independent explanation-quality gates remain closed; successful
execution is not evidence of a complete legal explanation.

The AsylG request also reproduced HTTP 500 when estimated total evidence size
produced more than three actual batches. Planning now fits whole change units
using the real partitioner before admission, keeps the full audit diff, and
reports limited coverage. Fifty-four analysis and backlog tests passed, including
1k/3k/4k/5k/12k context budgets, exact evidence coverage and an unchanged audit.
The exact API Ruff gate passed. Production replay remains pending activation.

## Cantonal identity and FAQ replay

Artifact identity now consumes the verified LexWork publisher, systematic number,
language and exact PDF version. This allows translated watch names without title
guessing. Live Basel-Stadt 122.510 and Bern 122.20 probes both verified their exact
official identities. Non-legal pages without official identifiers may establish
only probable continuity at the exact watched URL. Conflicting legal identities,
different page URLs and unknown uploads retain quarantine/confirmation behavior.
Twenty-five identity, LexWork and backlog tests plus exact API Ruff passed.

## Explicit daily document checks

Direct document watches now have a five-language daily-check control and next
eligible check state. Existing and newly created watches remain manual until an
administrator opts in. The scheduler admits at most five documents per tenant
and twenty tenants per pass through the existing durable ingest queue. It
coordinates with manual scans, rechecks pause/opt-in/active administrator status
before fetching, retains evidence on source failure and queues changed-document
AI independently. The control sends no email. Historical selected comparison
baselines do not replace the current live baseline for automatic checks.

Thirty-four document/identity/workflow/backlog tests passed, plus an existing-watch
migration round-trip test. Coverage includes CSRF, viewer denial, two populated
tenant isolation, queued opt-out/pause/operator revocation, bounded/idempotent
admission, source failure retention and separate AI work. Exact API Ruff and the
full frontend build passed, including shell, translations, resources, reports,
help and TypeScript checks. Browser verification against an isolated local app
confirmed opt-in persistence after reload, paused state, opt-out and the 390px
mobile layout. Test evidence was explicitly synthetic and never uploaded to the
pilot accounts. Production scheduled execution remains pending activation.

## Expanded live source audit

All 26 configured official legal/news source streams passed a bounded live health
and discovery probe. Twenty-one probes extracted one real selected artifact;
three historical Fedlex samples retained metadata only, and two bounded discovery
pages were empty. See [the dated source evidence](monitoring-v2/evidence/baseltech-official-source-probes-2026-09-21.json).
This does not enable every schedule or prove complete catalogue coverage.

The audit found and fixed three further source defects. Fedlex's `#lawcontent`
contains preamble and annex siblings outside `main#maintext`; HTML extraction v5
retains the whole legal container. OC 2026/483 now yields 28,118 German characters
instead of 272, including the annex. The French and Italian artifacts yield
28,542 and 28,365 characters. Reconciliation excludes dated JOLux Work members
before root-work keyset paging. Historical Bundesblatt Federal Archives links
are retained as explicit metadata-only references without following them or
weakening the publication-store URL check. The Federal Criminal Court parser
recognizes `Entscheid vom`; RR.2026.58 verified the cover date and retained 28,765
characters with its original PDF hash.

The expanded regression run also caught an interaction with language-specific
direct watches. Shared editions retain distinct document/expression identities
but now map to one provisional corpus work. Official connector binding explicitly
excludes private legacy mappings. Eighty-seven extraction, Fedlex, corpus, court,
workflow and backlog tests passed, including multilingual/pinned edition reuse,
private binding refusal, archive reference rejection and annex-only changes.
Exact API Ruff passed. Repaired pilot extraction baselines must be established
after activation before scheduled monitoring; these repairs are not legal changes.
