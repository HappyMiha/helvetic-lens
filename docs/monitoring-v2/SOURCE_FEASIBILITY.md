# Helvetic Lens Monitoring v2 — source feasibility review

Reviewed: **2026-09-10**. Coverage: ten use cases C1–C7, B2, B7, B8. This review of official documentation and public pages supports planning; it is not a successful end-to-end connector test. No accounts were created, terms were not accepted on behalf of the product owner, and authenticated keys/APIs were not tested. API documentation indicates integration feasibility without proving current operation from the future Helvetic Lens environment.

**Scope change, version 1.1:** the user classified C4 as a possible future feature and excluded it from development. Previous research findings for all ten cases are retained below; current work and source gates apply only to the nine active cases. C4 has no current discovery, API probe, licensing or delivery tasks.

## Backlog decision register

| Use case | Verified status | Decision before development |
|---|---|---|
| C1 — civil hazards | Official Alertswiss publication verified; supported public API/automated republication licence unverified | Discovery gate for acquisition channel, permissions and message lifecycle |
| C2 — public transport | Documented GTFS-RT API, API key, Protobuf, alignment with static GTFS | Implement after a sandbox contract test; reconcile contradictory limits |
| C3 — road traffic | Documented DATEX II/SOAP API with a key; special FEDRO terms | Build access/export rules into the platform; access renewal is an operational dependency |
| C4 — customs FX | XML exists, but the page explicitly restricts third-party use/distribution under SIX rights | **DEFERRED — possible future implementation; do not take into development.** Retain the rights finding only for a future decision; no v2.0 gate |
| C5 — pollen | Official CSV through STAC API, free use with attribution | Strongest candidate for the first complete vertical scenario |
| C6 — water | Official GraphQL API, measurements, live feed; contradictory live-window length documentation | Contract spike, watermark/reconciliation; separately investigate official flood warnings |
| C7 — air | NABEL: 16 stations; cantonal portals offer data/API, single live NABEL endpoint unverified | Pilot on a specific verified dataset; do not overstate geography |
| B2 — tenders | Official API, public publications/search without user auth; separate document access | API-first; separate publication-time, attribution, correction and gated-document rules |
| B7 — IP/trademarks | Official IPI API for trademark/patent data, signed terms + account | Begin arranging access; do not plan Swissreg scraping as the primary channel |
| B8 — auctions | Current official eGant website has public listings; API/feed/reuse permission unverified | Bounded discovery for read-only monitoring, rights and statuses; do not automate bids |

## C1 — Alertswiss / cantonal hazards

**Facts.** Alertswiss is a federal and cantonal channel; BABS/FOCP operates the infrastructure, and cantonal authorities usually create messages. Levels: alarm, warning, information; all-clear/expiry/removal end their current applicability. Coverage includes Switzerland and Liechtenstein. DE/FR/IT/EN are supported, but the publisher is not required to provide every translation. The responsible authority decides whether to publish an event. [Alertswiss FAQ](https://www.alert.swiss/en/faq.html).

**Unverified.** The reviewed official pages did not establish a supported external API contract, feed reuse terms, SLA or permitted poll rate. An unofficial JSON endpoint, even one used by the website, is insufficient proof.

**Planning.** The gate must provide a supported endpoint/channel, licence/reuse scope, issuer/event identifiers, territorial geometry, update/cancel/all-clear semantics and fixtures. Preserve official instructions with their source and language; distinguish translation/explanation from authority text. A missing/failed source does not become "no hazards". Additional cantonal sources require separate contracts and do not imply automatic complete coverage.

## C2 — opentransportdata GTFS-RT

**Facts.** The feed provides known realtime changes within a three-hour window for operators supplying realtime data; it is aligned with static GTFS. An API key is required. The cookbook documents Protobuf, redirects, a 30-second cache and a maximum of two requests per minute; JSON is intended for testing. [GTFS-RT cookbook](https://opentransportdata.swiss/en/cookbook/realtime-prediction-cookbook/gtfs-rt/). The general limits page instead states five requests/minute for GTFS RT and service alerts. This is an explicit documentation conflict, not grounds to silently choose the higher limit. [Limits and costs](https://opentransportdata.swiss/en/limits-and-costs/).

**Terms.** General Open Data terms permit processing and publication; service-based data requires registration. Attribute the source, keep raw data current and publish original analyses in your own name. FEDRO terms apply separately to road data. [Open Data terms](https://opentransportdata.swiss/en/terms-of-use/).

**Planning.** Global shared fetch/cache for all watchlists, Protobuf adapter, static GTFS versioning, stop/trip/date matching, unknown-realtime fallback. Initial conservative limit: no more frequently than every 30 seconds per shared feed; confirm actual grant/429 behavior. Test discrete service alerts and trip updates separately. Complete trip coverage does not imply complete realtime data for every operator.

## C3 — ASTRA / FEDRO traffic

**Facts.** The official API delivers current road situations in DATEX II through SOAP; an API key and SoapAction are required. It includes updates, revocations and planned roadworks. A revoked situation remains available for 60 minutes; no history API is provided. [Traffic situations cookbook](https://opentransportdata.swiss/en/cookbook/road-traffic-cookbook/traffic-situations/).

**Terms.** FEDRO terms as of June 2026 require registration, provide standard access for six months and allow justified renewal. Partner access has separate terms. Sharing raw data with third parties through a machine-readable interface is prohibited. Published processing results require FEDRO TDP attribution; behavioral profiling and reidentification of people on roads are prohibited. [FEDRO terms](https://opentransportdata.swiss/en/tac-fedro/).

**Planning.** Per-source `allow_raw_export=false`; no generic raw JSON/API/export for this source. Verify the permitted derived-field set before the user API gate. Retain rights policy with the source/record, monitor credentials/access expiry and plan renewal before six months. History requires a local event ledger under permitted retention policy; event identity and revocation reconciliation are mandatory.

## C4 — BAZG customs exchange rates (DEFERRED)

**Facts.** The official page offers daily rates and XML. It explicitly identifies SIX Financial Information copyright and prohibits third-party use/further distribution; availability of daily rates is not guaranteed. [BAZG Devisenkurse](https://www.bazg.admin.ch/de/devisenkurse-verkauf).

**Future possibility.** There is no current work or v2.0 blocker; even a link-out placeholder is not required. Source-rights verification is needed only after a new explicit user decision to restore C4; the rights issue does not prove technical unsuitability of XML. Future discovery must establish permission to acquire, store, display, issue threshold alerts, commercially redistribute, export and retain history, plus an owner and cost. A licensed alternative rate must not silently be labelled the BAZG customs rate. After that gate, base/quote currency, unit multiplier, value date, effective date and non-trading-day semantics are required as distinct concepts.

## C5 — MeteoSwiss pollen

**Facts.** The national network has 15 stations; since 2023 it has provided automatic hourly measurements for seven pollen groups. Historical and automatic measurement methods differ and must not be mixed directly. The official STAC API provides station CSV files; OGD can be used with MeteoSwiss attribution. [Pollen stations](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations). The changelog dated 17.07.2026 confirms that hourly `h_now` files update every 20 minutes. [Pollen cadence change](https://opendatadocs.meteoswiss.ch/changelog/1.2.0).

**First implementation gate MV2-069.** These sources verify the observation dataset; a separate usable official forecast channel, its rights and station/allergen coverage are not yet established. G(C5-forecast) requires its own dated contract and permitted live sample before accepting complete Pollen Watch. A forecast mock does not close this gate; it is a specific first-delivery risk.

**Planning.** Determine station applicability, observation time and publication time separately. Twenty minutes is the file-update interval; hourly is the measurement granularity. A missing taxon/value does not mean zero. Threshold watchlists refer to a specific taxon, station/justified area, unit and rolling window. Do not promise personalized medical assessment or street-level precision everywhere. Verify anonymous STAC fetch from the deployment environment, unit metadata and current infrastructure terms.

## C6 — FOEN / BAFU water and floods

**Facts.** Official documentation describes GraphQL for hydrological observations, station metadata, aggregates and a live feed. It includes provisional/validated/definitive releaseState. Queries are limited to 10,000 rows; excess is rejected rather than truncated. Documentation conflicts: the introduction mentions a 7-day live window, while a note states that `data_live` does not return rows older than 12 hours. The note also specifies a 9–19-minute measurement-availability delay. [Water observations](https://api.data-platform.cloud.bafu.admin.ch/dataproduct-water-observations). The platform licence permits commercial and noncommercial use with the author, title and a link to the dataset. [BAFU licence](https://api.data-platform.cloud.bafu.admin.ch/en/lizenz-und-quelle).

**Planning.** Contract-test the actual live window, pagination, UTC timezone, corrections and data freshness before committing an SLA. Bind stable water-level/discharge/temperature thresholds to station, parameter and unit. Measurements, flood forecasts and official danger warnings are separate source types; the first does not replace the other two. Temperature/discharge measurements do not establish that water is suitable for swimming. Absence of a warning feed must not lead to a "safe" conclusion.

## C7 — NABEL / cantonal air

**Facts.** NABEL measures pollution at 16 stations representing different conditions; current-year values are provisional. [NABEL data query](https://www.bafu.admin.ch/en/data-query-nabel). The Basel-Stadt cantonal portal has a specific Basel-Binningen dataset with API/export tabs and fields for O3, NO2, PM10, PM2.5 and other quantities. The public table also contains gaps: a timestamp does not guarantee a value for every pollutant. [Basel-Binningen dataset](https://data.bs.ch/explore/dataset/100051/table/).

**Unverified.** This review did not establish a single officially documented NABEL live measurements API, current cadence for this cantonal dataset, its rights or national coverage. A station-location geoservice is not an API for current measurements.

**Planning.** The gate selects specific station datasets with a machine-readable endpoint, licence, pollutant units, interval definitions and freshness contract. Show pilot canton coverage explicitly to users. Distinguish numeric observation, short-term air-quality index and regulatory annual limits; a threshold has an explicit aggregation duration. Do not present the product's environmental signal as official medical guidance.

## B2 — SIMAP procurement

**Facts.** The official FAQ links to API documentation and an API client application. UI access to tender documents requires login, a company role and an interest declaration. [SIMAP FAQ](https://www.simap.ch/de/help/faq). API terms permit publications/search without user authentication; other access follows account roles. Commercial reuse of publication data is permitted, but substantive content must not be changed and commentary must be visually separated; disclaimers, quality notices and publication of corrections are required. Data may be disclosed to third parties from 08:00 on its publication day. Terms must flow through to recipients. The API is currently free; future changes are possible. [SIMAP legal / API terms](https://www.simap.ch/de/about/legal).

**Unverified.** The Swagger page exists as an address, but the text browser did not extract its schema; exact endpoints, quotas, client setup and protected-attachment scope require a contract spike. Anonymous publication search does not establish anonymous attachments.

**Planning.** Machine-readable source policies: `publication_not_before`, original/commentary separation, correction propagation, access tier. Normalize CPV, canton, buyer, deadline, currency/value when available, lots, award/cancellation/amendments. Set calendar timezone to Europe/Zurich after provider verification. Do not automatically make an interest declaration on behalf of the user. Gated documents remain links to permitted access until another flow is agreed.

## B7 — IPI / Swissreg trademarks and patents

**Facts.** IPI officially provides trademark and patent records through a free API after terms are signed; the page links to technical documentation. [IPI data delivery API](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/ip-daten/datenabgabe-api). Terms require an account and signed acceptance; credentials must not be shared with third parties. Use for mailings is prohibited; raw data redistribution passes obligations to the recipient; the product must not imply that its data offering is official. [IPI data-delivery terms](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/d/Nutzungsbedingungen-Datenabgabe.pdf).

**Coverage.** Swissreg contains active CH trademarks/applications and certain deleted records, plus international marks designating CH. New CH applications usually appear within six working days; publication search is limited to CH marks. The database does not guarantee exhaustive detection of similar/conflicting marks. [Swissreg trademark coverage](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/datenbanken-und-verzeichnisse/swissreg/markendatenbank).

**Planning.** The spike obtains account grant, scopes, quotas, delta/continuation, update cadence and sample fixtures. Mapping API scope against UI coverage is mandatory. Clarify the provider restriction "mailings" for user-requested monitoring channels before launching email alerts; do not independently interpret it as automatic permission. Produce explainable candidate matches using words, owner, Nice classes and publication changes; do not automate an "IP infringement" conclusion. Generic raw export must inherit source terms.

## B8 — official Ticino auctions

**Facts.** The current official Aste UEF website publishes online lots with current prices, bid counts and closing times. [Aste UEF listings](https://www.aste.ti.ch/it/). Current eGant terms dated 09.04.2026 describe registration for participation, an automatic bidding agent on the platform itself, binding bids, and possible termination of an auction together with the proceedings. [Aste UEF terms](https://www.aste.ti.ch/it/condizioni_generali). An old official 2010 announcement stating that online bids were unavailable cannot describe current eGant behavior.

**Unverified.** Supported public API/RSS, reuse permission, permitted cadence, coverage of separate in-person/real-estate auctions and availability of a complete archive. A public price does not grant a licence for bulk acquisition.

**Planning.** Discovery must separately map eGant movable lots and official real-estate/in-person auction notices if required by scope. After the rights gate, implement a read-only listing monitor with ID, canton/office, category, place, deadline/status and changed/cancelled/relisted states. Product deadline reminders use the current closing-time revision. Bids, participation registration and payments are outside monitoring scope. Parser/browser fallback is permitted only after rights verification, under a contract with schema-drift detection and without bypassing access controls.

## Shared acceptance gates arising from the review

1. **Source registry before ingestion:** publisher, exact dataset/API, purpose, access grant, licence URL/version/check date, polling limit, publication delay, attribution, raw/derived export permission, retention, source timestamp contract, scope/coverage.
2. **Connection proof:** permitted sample fetch from the target environment, schema fixture, auth failure/rate-limit behavior, empty versus failed response, source corrections/removals, latency measurements. Documentation alone does not replace this proof.
3. **Rights enforcement end to end:** restrictions apply to UI, alerts, downloads, organisation sharing, API, evidence snapshots, logs and support tooling. ASTRA raw-data restriction and SIMAP publication gate are specific regression cases.
4. **No global SLA from scrape cadence:** measure upstream publication lag, ingestion lag, matching lag and delivery lag separately; the user promise cannot be faster than the source. Reference examples: hourly pollen updated every 20 minutes; IP publication may lag by working days; historical/live windows differ.
5. **Closure outcomes:** each source discovery ends with `approved implementation contract`, `approved scoped alternative` or `blocked with named external dependency`; the UI reflects capability availability instead of hiding source blockers as empty results.
