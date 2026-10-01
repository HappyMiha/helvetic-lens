# Independent source access

Status: implemented and locally validated (1 October 2026); Core activated as `e97043209b7a` on 1 October 2026.

One native research pipeline discovers, gates, reads and analyses public sources.
Direct catalogue requests and public source URLs remain usable when the selected
broad-web provider fails. SearXNG and Search1API share a bounded result contract;
choosing one never silently invokes the other or spends paid fallback credits.

Scope: Core shared by Legal and Pharma; private local SearXNG deployment; truthful
channel coverage; the existing consent, membership, source reader and request budgets.
No new end-user configuration fields. Catalogue metadata is discovery, not captured
full text or verified evidence. No claim of whole-internet coverage.

Acceptance: configured local search returns real public candidates; controlled
provider outages preserve direct candidates through native gate/read/analysis;
malformed results and private URLs are rejected; empty and unavailable differ;
request reservations reflect selected channels; both products work without a
Search1API key. Run affected checks, API lint and backlog guard, then verify deployment.

## Operation

Production defaults to `WEB_SEARCH_PROVIDER=searxng`, with the internal endpoint
`http://searxng:8080`. `search1api` deliberately selects the existing paid adapter;
`none` uses only direct discovery. No automatic paid fallback. API, native workers
and scheduler inherit the same production settings. SearXNG exposes a local-only
operator interface at http://127.0.0.1:18880 and is not published through the website.

The pinned official container runs Google, Bing and Yahoo, one result page,
10-second engine timeouts, bounded CPU/memory and JSON responses. Configuration
and a generated signing secret persist in named Docker volumes. Secrets never
enter Git or logs. Search queries still go to external engines; local hosting does
not make web queries private. Backend selection is operator configuration.

Crossref publication metadata is queried directly for both products, with Europe
PMC for Pharma and Fedlex title search for Legal. Explicit public URLs from the
question also enter the existing gate/reader. Catalogue coverage is limited to its
own corpus; full text, robots, access rights and source relevance are checked by
the existing reader and decision pipeline. Fedlex title search benefits from short
German/French/Italian terms. It is not a general legal full-text search engine.

Reservations count the maximum selected provider API requests: balanced SearXNG
uses three (one broad request plus two direct catalogues); balanced Search1API
uses four; direct-only uses two. A SearXNG request fans out to at most the configured
engines (three in production). Daily and per-investigation limits are preserved.
Failed channels do not erase successful candidates or imply no relevant evidence.
Partial SearXNG success exposes returned candidates and separate failed engines
using the existing client coverage display. No client rebuild is required.

## Acceptance evidence

- Controlled native Legal and Pharma investigations completed with the broad
  provider unavailable and no Search1API key: direct candidates passed through the
  existing decision gate, reader, evidence extraction and claim comparison.
- Adapter checks cover bounded responses, malformed data, unsafe URLs, failed
  versus empty channels, submitted URLs during discovery failure, signed source
  receipts, request accounting and private-search erasure without quota renewal.
- Real free search from this server on “building material reuse barriers” returned
  candidates from Google/Bing/Yahoo. The configured adapter accepted 12 candidates;
  direct Crossref returned 11 safe publication records. DuckDuckGo/Brave/Qwant
  refused this host during initial checks and are not configured. No paid provider
  or private source was called. Live semantic/model quality was not re-evaluated.
- Affected API tests, API lint and backlog guard pass. Required automatic release
  gates and deployed configuration/source identity will be checked after push.

References: [official SearXNG container setup](https://docs.searxng.org/admin/installation-docker.html),
[search API](https://docs.searxng.org/dev/search_api.html),
[Crossref REST metadata](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).
