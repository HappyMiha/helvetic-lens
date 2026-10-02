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

As amended by the owner on 1 October, direct catalogues and local SearXNG have
no application daily or per-investigation query quota. Only configured paid
Search1API dispatch reserves an allowance (two broad requests for balanced search,
plus explicitly requested alternatives). Exhausting that allowance skips the paid
channel and keeps free sources available. Telemetry separately records all source
requests, including the court adapter's three HTTP requests. Provider throttling,
configured SearXNG engines, source permissions and execution timeouts remain.
See [expanded sources and memory](RESEARCH_SOURCES_MEMORY_AND_UPDATES.md).
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

## Legal Feed service integration

2 October 2026: the owner requested reuse of Legal’s free engine for Legal Feed
after its separate Search1API account reached zero credits. The dedicated POST
`/api/integrations/legal-feed/search` accepts only a bounded public query and
returns normalized public discovery records plus partial-engine status. A separate
`LEGAL_FEED_SEARCH_TOKEN` must match the server Authorization header; no token
means access is disabled. It grants no user session or private-data access.
SearXNG stays local-only. Engines and upstream URL are operator-controlled; no
paid fallback, AI call or dossier creation occurs. A shared 30-request/minute
burst guard protects the existing engine without introducing a daily allowance.

Acceptance: exact service authentication, private-route isolation, bounded input,
burst throttling and sanitized engine failure; verify real production results
and subsequent Legal Feed monitoring after deployment. Local acceptance passes:
3 machine-integration tests, 11 existing search-adapter scenarios and the backlog
guard; API lint passes. Production activation remains pending. This does not close broader source coverage gates.
