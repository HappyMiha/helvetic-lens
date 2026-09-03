# Swiss Federal Supreme Court connector

HL-041 uses only the Swiss Federal Supreme Court's official public decision service. It does not treat an aggregator as the authority of record.

## Source contract

- `latest` rereads the official “new decisions” index and walks the five newest insertion-date pages in bounded item slices. This deliberate overlap catches late observations without duplicating immutable versions.
- `reconcile` walks every insertion date from 1 January of the previous year through today, one bounded date page at a time, and then starts a new cycle.
- The sitemap declared by the court's `robots.txt` describes the public website. It does not contain the decision database or per-decision `lastmod` values. The earlier roadmap assumption about official yearly decision sitemaps was therefore removed; current and previous year coverage uses the official date index instead.
- The giant all-decisions RSS response is not used for polling.
- `robots.txt` is checked as part of health. Its published two-second crawl delay is also the connector's hard minimum between HTTP requests.

## Identity and evidence

Each work retains the exact `aza://` identity, normalized docket, canonical official search URL, official JumpCGI link, court and chamber, actual DE/FR/IT decision language, decision date, separate insertion/publication date, subject-area descriptors, publication-intended marker, retrieval provenance, and SHA-256 of the official HTML.

The authoritative HTML is stored as the immutable artifact and extracted through the dedicated decision-content boundary. Helvetic Lens does not invent a PDF when the free official source publishes only HTML.

Exact SR/RS identifiers and article-plus-act references found in the decision are retained as evidence-backed `cites` candidates. Article references are grouped by act to avoid a noisy relation per occurrence. A judgment can cite or interpret a statute; it never creates an `amends` or `repeals` relation for statutory wording.

## Failure boundary

Challenge pages, a missing decision body, docket/date mismatches, changed templates, an altered crawl policy, and an empty interval linked from the latest index degrade the connector without advancing uncertain coverage. Each decision is committed independently, so a bad item leaves a retryable error and resumes from the same safe page position.

`POST /api/connectors/federal-court/latest/sync` and `POST /api/connectors/federal-court/reconcile/sync` each run one persisted page. `scripts/check_federal_court_connector.py` performs a bounded read-only live check without writing to the corpus.
