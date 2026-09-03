# Versioned official connector contract

HL-038 provides one ingestion boundary for Fedlex, the Swiss Parliament, the Swiss Federal Supreme Court, and later official sources. A connector is an adapter around an authority contract; it is not a one-off patch for an individual law URL.

## Operations

Every `OfficialConnector` implements:

1. `discover_since(cursor, page_checkpoint)` for one bounded catalogue page;
2. `fetch_metadata(reference)` for identity, document kind, status, dates, and provenance;
3. `list_expressions(metadata)` for the source languages and immutable version keys;
4. `fetch_official_artifact(expression)` for the canonical HTML/PDF/XML evidence;
5. `extract_relations(metadata)` for explicit, evidence-backed authority relations;
6. `health()` for reachability and source-contract status.

The manifest pins the connector and source-schema versions, authority, official host allowlist, attribution, rate floor, and expected source contract. Every receipt records those versions so a parser change does not erase which rules produced an earlier import.

## Normalized persistence

The runner accepts a stable external identity, source revision, authority identifier, document kind, actual language, official dates/status, canonical URL, artifact hash, raw provenance reference, and attribution. It merges them through the shared `RegulatoryCorpus` boundary.

Official artifacts are streamed under the configured byte limit, hashed before use, stored by digest, and extracted through the same bounded HTML/PDF/text parser as direct monitoring. The normalized version retains extracted text, passages, content type, filename, extractor revision, canonical artifact URL, and both text and binary hashes. Redirects are revalidated against the connector's HTTPS host allowlist.

## Cursor and recovery semantics

PostgreSQL stores one global `ConnectorState` per connector stream and one immutable page identity derived from the input cursor, output cursor, raw page reference, schema version, and discovered source revisions.

- The source cursor advances only after every item in the page has committed.
- Each successful item updates a safe `next_index` checkpoint in its own transaction.
- A failed item stores its identity, attempt, bounded error, retryability, and raw reference. The page becomes `partial`; the source cursor stays unchanged.
- Retry starts at the failed item. Receipts uniquely key connector, stream, external identity, expression, and source revision, so re-delivery is harmless.
- Committing the same complete page again returns its saved result without duplicating corpus records or fetching its artifacts again.

The connector runner never holds a database transaction open while waiting for official metadata or artifact downloads.

## Shared transport and drift handling

`ConnectorHttpClient` applies public-address validation, official-host redirect validation, streamed content limits, timeout, three bounded attempts for transient HTTP/network failures, exponential delay with jitter, connector rate floors, and one redacted integration diagnostic per attempt. Binary diagnostic bodies remain size/hash metadata through the existing logging boundary.

Missing required identity or schema fields, an unexpected schema version, a non-advancing non-terminal cursor, malformed expected JSON/XML/HTML, or an implausibly empty page yields `connector_contract_drift`. The connector state becomes `degraded`; Helvetic Lens does not mark the catalogue unchanged, infer repeal, or advance its cursor.

`GET /api/connectors/status` exposes saved connector version, schema version, health, cursor/checkpoint, source-contract observations, and last start/completion/success times. Known official connectors appear as `unknown` before their first persisted run.

## Official source probes

The repository includes fixture-backed probes for the three first source contracts and a read-only live command:

```powershell
services/api/.venv/Scripts/python.exe scripts/check_official_source_contracts.py
```

On 3 September 2026, the bounded Fedlex RSS and Federal Supreme Court latest-index probes passed. The Swiss Parliament JSON endpoint returned HTTP 403 from this development network, so its live state was correctly reported as `degraded`. The official endpoint and JSON fixture remain part of the contract, but HL-040 cannot be accepted on a deployment network until its live probe succeeds. A fixture is regression evidence, never proof that an official source is currently reachable.

Concrete discovery and reconciliation rules are implemented in HL-039 (Fedlex), HL-040 (Parliament), and HL-041 (Federal Supreme Court). Each uses this runner and must add its own fixture corpus and live smoke evidence without weakening these common guarantees.
