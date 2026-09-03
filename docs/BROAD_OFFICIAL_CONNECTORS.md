# Broader official-source connectors

HL-050 extends the shared HL-038 ingestion pipeline. It does not add another crawler, evidence store, or notification path. Every item uses the same immutable artifact, normalized work/expression/version, event, relation-candidate, schedule, retry, and integration-log contracts as the core connectors.

## Source contracts

| Connector | Official discovery source | Coverage | Default cadence | Identity and cursor |
| --- | --- | --- | --- | --- |
| Federal news | News Service Bund JSON search at `d-nsbc-p.admin.ch` | Federal Council, departments, offices, regulators, and consultation notices in DE/FR/IT/RM/EN | 30 minutes for DE/FR/IT; hourly for RM/EN | language-group ID; fixed date window, offset paging, and overlapping timestamp watermark |
| FINMA news | FINMA's official language-specific RSS feeds | FINMA news, guidance, enforcement, and sanctions notices in DE/FR/IT/EN | hourly | canonical official item URL; two-day overlapping publication watermark |
| Fedlex consultations | Fedlex JOLux `Consultation` catalogue through the official SPARQL endpoint | consultation status, opening/deadline, responsible institution, draft links, and declared `foreseenImpactToLegalResource` relations | six hours | consultation URI; complete bounded keyset reconciliation cycle |

Federal news and FINMA records are `official_notice` works with `notice_context_only=true` and lifecycle `published`. Fedlex consultation records are `consultation` works with `proposal_not_enacted_law=true` and the exact official status URI retained. None of these records are shown as enacted law.

## Evidence and impact behavior

- Federal and FINMA discovery payloads determine identity and revision. Their canonical official HTML pages are downloaded and retained as immutable source artifacts.
- Each Fedlex consultation language expression retains the original SPARQL JSON response as its immutable official artifact. The generic JSON extractor indexes it without rewriting the saved bytes.
- The official Fedlex `jolux:foreseenImpactToLegalResource` predicate creates a confirmed `potentially_impacts` relation with its predicate and endpoints recorded as evidence.
- Other possible relations continue through the HL-044 deterministic identifier/full-text candidate generator. A candidate is not displayed as a legal conclusion without the existing evidence rules.

## Failure and load boundaries

All HTTP calls use the connector allowlist, response-size limit, redirect policy, rate control, three bounded transient retries, and redacted integration logs. Cursor advancement occurs only after the page commits. Contract validators fail visibly when required JSON/RSS fields disappear. The schedules page exposes every stream and lets a platform administrator pause, retime, or trigger it.

The fixture-backed verification covers paging/cursors, overlap, receipt deduplication, raw artifact retention, exact consultation relations, and schema drift. `scripts/check_official_source_contracts.py` performs bounded live health probes; it never starts a catalogue crawl.
