# Sources, memory and understandable dossier updates

Owner request, 1 October 2026: implement diagram blocks 1, 2, 3, 6 and 7 together.
Status: implemented and locally verified; production activation tracked separately.
Scope belongs to MV2-020/023 with existing source, evidence,
monitoring and reader dependencies; broader parent acceptance remains open.

## User outcome

A research question discovers accessible original records, reads supported online
documents and contributed files, recalls relevant dossier knowledge through text,
meaning and evidence relationships, and explains what each monitored change adds
to the dossier. Both Legal and Pharma use the same implementation. Technical
source/model choices remain behind the existing simple question and contribution
flows. Monitoring still requires a separate explicit action.

## Implementation and acceptance

1. Extend registered direct public discovery beyond current catalogues with
   official regulatory, trial and legal/court sources. Report exact adapter scope,
   skipped channels, empty responses and failures. Existing feed/page connections
   remain usable independently of the configurable broad web lane. Internal-system
   connections require the owner's service identification and authorized access;
   do not claim coverage of an unconfigured enterprise system.
2. Share bounded local document processing between contribution and public readers:
   HTML/text/PDF, scanned-page OCR, Office XML documents with table/cell locators,
   and email originals/attachments. Retain original hashes, extraction method,
   limits and exact extracted passages. Never execute active document content,
   follow email links, leak private text to discovery, or infer perfect OCR accuracy.
3. Compose lexical, local multilingual semantic and evidence-relationship retrieval
   over the current authorized ledger, including historical and reviewed evidence.
   Reuse the existing vector cache and original records. Connect it to automatic
   research recall as well as saved search, with resumable preparation, explicit
   fallback, bounded context selection and revocable source dependencies. No hidden
   lexical prefilter may exclude semantic candidates. Preserve contradictions.
4. Present a clear answer and source-backed explanation of what changed, why it
   affects the question, contradictions, open gaps and human-review requirements.
   Use the existing dossier and monitoring readers without another settings form.
5. Apply one current-permission coverage/change projection across saved page,
   feed and recurring-web research. Unchanged sources do not require repeated
   synthesis; failed checks never imply no change. Update and notify through
   native authorized jobs/events and retain retry/idempotency/revocation fences.

## Boundaries and delivery

Reuse PostgreSQL, local embeddings, relational evidence links, native files/jobs,
Jev/Laya, the configured synthesis client and existing production sites. Adding
named infrastructure is unnecessary when an existing component meets its function.
Do not alter model routing in blocks 4/5, thresholds, source rights, public consent,
nine Monitoring sections, retired hosts, Apache-2.0 or deferred directions.
No paid inference, private production research, production fixture dossiers or
browser automation. Verify a neutral fictional end-to-end path, important failures
and the repository's required gates on final code; then commit/push main and
verify normal activation. Do not publish unfinished substeps or report-only releases.

## Implemented boundaries

- Direct adapters: Crossref, Europe PMC, Fedlex title catalogue, ClinicalTrials.gov
  API v2, openFDA labels, current EMA/FINMA RSS entries and the Federal Supreme
  Court's latest publication day. Recent feeds/indexes are explicitly not archive
  search. Configured native archive collectors remain independent. Provider
  telemetry records the court adapter's three bounded requests without charging
  a paid-search allowance.
- Official contracts: [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api),
  [openFDA labels](https://open.fda.gov/apis/drug/label/how-to-use-the-endpoint/),
  [EMA feeds](https://www.ema.europa.eu/en/news-events/rss-feeds), and the existing
  native FINMA/Federal Court connector contracts. Adapters do not establish full
  coverage, regulatory approval, or source availability.
- Shared offline reader: TXT/Markdown/CSV/HTML/JSON/PDF/DOCX/XLSX/PPTX/EML;
  2 MB contributed files, 1 MB anonymous fetches, 24,000 extracted characters,
  20 opening PDF pages, at most four scanned pages via local Tesseract, ten MIME
  attachments and bounded ZIP expansion. Source formats retain exact extracted
  locations, original hashes, partial extraction and parser/OCR limitations.
- Semantic preparation reuses the native evidence-vector cache: 16 passages per
  saved checkpoint and eight preparation batches per automatic episode, up to
  20,000 eligible public passages. A later episode or saved search resumes the
  cache. Incomplete/unavailable semantic preparation falls back explicitly to
  lexical and cited-relationship retrieval. No lexical prefilter hides a semantic
  candidate. Current permission checks remain authoritative before and after work.
- The graph adds cited one-hop relationships and a finding's contrary/supporting
  evidence, bounded to 2,000 relationships. It does not merge people by name.
  Private/mixed findings never enter the public planner's memory.
- Native page/feed/web check histories and private notifications share the current
  evidence/review/coverage reading. Explanations compare actual quotations;
  unchanged successfully analysed material is not a new analysis or notification.
  Failed checks remain explicit gaps. Existing per-account following and monitoring
  consent remain separate from initial research and public publication.

Internal enterprise connections still require the owner's system/API identification
and authorized access. No unconfigured CRM, DMS or authenticated archive is claimed.
Local validation: both clients passed 457 tests, lint, type checking and production
builds. Controlled API/worker scenarios cover official-source normalization and
failure scopes, document/table/email parsing, exact cited graph retrieval, semantic
recall and fallback, contribution revocation, unchanged monitoring, current review
and source visibility. A real scanned PDF passed local Tesseract extraction through
an isolated runtime. The initial affected API failures were repaired and rerun;
subsequent source/reader/recall checks passed, including both complete exploration
journeys and free discovery with a zero paid allowance. Final quota, history, paid-provider, source inspection and recurring-monitoring
checks passed (13 + 3 focused cases). Exact lint and the backlog guard passed.
Production activation is recorded in the parent release checkpoint; local
fixtures do not establish live professional answer quality.

Free source queries have no application query quota. Existing paid-search
allowances remain unchanged and cannot block direct catalogues or SearXNG.
Native file readers report missing OCR separately when runtime tools are absent.

## Owner amendment: free discovery has no application query quota

The owner requested removal of free-service limits on 1 October. Direct public
catalogues and local SearXNG must not consume either daily paid-search reservations
or the episode's paid-search allowance. An exhausted paid channel is omitted with
an explicit receipt while free sources continue. Rotating saved-search history
must not impose a same-day search quota. Explicit source inspection has no
three-source count cap; completed reads remain idempotently cached. Provider throttling, current source rights,
request timeouts and finite research/model execution remain operational boundaries.
Acceptance: a zero/exhausted paid allowance still completes free discovery in both
products; paid dispatch remains reserved and cannot exceed its allowance.
