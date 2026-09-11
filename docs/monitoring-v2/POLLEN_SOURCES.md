# MV2-069 — Pollen source dossier, revision 1

Captured 2026-09-11. **IN PROGRESS; neither source gate is accepted yet.**
The retained [decoded proof](evidence/mv2-069-source-proof.json) is evidence of
access and an offline decoding experiment, not an operating collector or a live UI.

## Observation channel

Official [pollen documentation](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations),
[download conventions](https://opendatadocs.meteoswiss.ch/general/download) and
[STAC collection](https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-pollen).
The downloaded station CSV contains **15** station records. Collection prose said
16; use the exact inventory, and resolve the discrepancy before claiming coverage.
Only Basel PBS hourly bytes were sampled; metadata for another station is not a
verified live observation at that station.

The CSV delimiter is semicolon, encoding Windows-1252, decimal separator point;
`reference_timestamp` is parsed as `dd.mm.yyyy HH:MM` in UTC. Hourly automatic
measurements and historical manual/daily series remain separate identities.
The documented `h_now` refresh is every 20 minutes; one capture does not validate
cadence over time. Daily `d0`/`d1` periods must not be substituted for hourly data.

| Allergen | Hourly parameter | Forecast variable documented in the official demo |
|---|---|---|
| Alder | kaalnuh0 | ALNUsnc |
| Birch | kabetuh0 | BETUsnc |
| Hazel | kacoryh0 | CORYsnc |
| Beech | kafaguh0 | No corresponding variable established |
| Ash | kafraxh0 | No corresponding variable established |
| Oak | kaquerh0 | No corresponding variable established |
| Grasses | khpoach0 | POACsnc |
| Ragweed | No current automatic hourly parameter established | AMBRsnc |

PBS's latest retained row is **06:00 UTC**, retrieved at **06:42:35 UTC**:
grasses 3, the other six parameters 0. Age at fetch is 2,555.962308 seconds;
this does not remain a fresh reading when replayed later. Preserve blanks as
missing. Reject an unrecognized missing marker until its meaning is established.
Categories/threshold scales are still unverified; do not invent labels from numbers.

Follow-up 2026-09-11: the official
[threshold table](https://www.meteoswiss.admin.ch/dam/jcr%3Af3d0942c-b3ab-4de6-882e-5df909faed9c/threshold-values-for-pollen-load-classes-of-allergenic-pollen-types.pdf)
specifies **mean daily** concentrations. It is not an hourly scale. The
[pollen information page](https://www.meteoswiss.admin.ch/climate/the-climate-of-switzerland/pollen-information.html)
also distinguishes the pre-2023 manual method from automatic measurements.
Retain the table as a candidate reference; do not activate its thresholds for
hourly automatic observations or instantaneous model values without a matching
method/period contract. No numeric threshold from that PDF is implemented yet.

## Separate forecast channel

Official [model documentation](https://opendatadocs.meteoswiss.ch/e-forecast-data/e2-e3-numerical-weather-forecasting-model),
[pollen decoding example](https://github.com/MeteoSwiss/opendata-nwp-demos/blob/main/10_icon_ch2_pollen_forecast.ipynb)
and [ICON-CH2 collection](https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-forecasting-icon-ch2).
The sampled parameter inventory includes **AMBRsnc** and **DEN**. Other pollen
variables in the example are seasonal capabilities, not available current forecasts.
Their absence cannot be filled with zero or a mock.

Use STAC search with an explicit UTC reference time, variable, control member
(`forecast:perturbed=false`) and lead. REST `latest` returned 400 in this probe.
The retained issue is **2026-09-11 00:00 UTC**, valid **06:00 UTC**. Pollen and
density items have separate identities and hashes. Signed asset URLs are temporary;
the proof records stable STAC identities instead. Item expiry was the next day;
retain retrieved evidence before upstream removal rather than promising URL permanence.

The offline decoder checks the same grid UUID, vector length, issue/valid time,
lowest model layer 80 and units. It multiplies pollen number/kg by matching DEN
kg/m³. CLAT/CLON are cell-centre degrees with the same grid UUID. Nearest-cell
mapping uses public station coordinates with a 5 km maximum mapping distance;
that bound is a product check, not model accuracy. All 15 catalogued stations map
within 1.6 km for this capture. These are **model estimates near stations**, never
measurements at those stations or at a person's home.

At PBS the retained ragweed estimate is approximately **0.9813 number/m³**.
Do not compare it to observed grass or claim that this single ragweed capture
proves birch/grass forecast acceptance. Preserve raw calculation precision as
evidence and round only display copy after an approved scale is available.

The initial decoder experiment used native ecCodes 2.47.3 with COSMO 2.47.0.1
and emitted a compatibility warning. On 2026-09-11 the retained bytes were decoded
again using matching native/Python ecCodes 2.47.0, unchanged official COSMO
v2.47.0.2 and numpy 2.4.3. No compatibility warning was emitted or suppressed.
Observation, all 15 forecast station mappings/values and source provenance are
identical to the initial result. The decoder now rejects mismatched releases
before reading GRIB and records versions plus the definition-tree SHA-256.
The [isolated build recipe](../../scripts/pollen-decoder/README.md) pins the base
image, all 92 Conda package artifacts/hashes and the upstream COSMO archive.
This resolves the technical version mismatch; it does not validate seasonal
coverage, categories, model accuracy or production operating behavior.

## Rights and open gates

Both source collections identify CC BY 4.0. The reviewed
[MeteoSwiss terms](https://opendatadocs.meteoswiss.ch/general/terms-of-use) require
attribution; use **Source: MeteoSwiss**, a terms link and identification of derived
model conversion. No endorsement is claimed. Public-data licensing is the basis
for this bounded source capture, not a claim that every operating obligation has
been implemented. Capture tools fetch public resources explicitly, have a 64 MiB
per-file bound, verify provided SHA-256, and resume only unchanged retained bytes.

| Gate still open | Owner and next action |
|---|---|
| Infrastructure usage and lifecycle | Integration: complete FSDI/CSCS terms dossier, bounded polling/retry plan and repeated freshness/correction samples |
| Official category semantics | Integration: retain the authoritative scale, units and aggregation period per allergen; review whether the same scale applies to forecasts |
| Required birch/grass forecast evidence | Integration: establish seasonal availability and a permitted retained official sample; never replace with ragweed or synthetic data |
| Rights enforcement | MV2-070/030: implement attribution, evidence retention/deletion policy and permitted display/notification behavior |
| UX and full product | MV2-069/031/071: prototype review, working journey and independent acceptance |

Until these pass, source-backed Start/notifications remain disabled. Independent
configuration, state contracts and labelled prototype work may continue while
the source gates, previous tests and deployment remain pending.

## Reproduce the bounded experiment

### Infrastructure terms follow-up — 2026-09-11

[FSDI terms](https://www.geo.admin.ch/en/general-terms-of-use-fsdi) allow
registration-free acquisition under fair use and the dataset's own conditions.
Use download services for retained datasets, share fetches across users, cache
unchanged content and adapt to interface updates. Access can be restricted for
excessive use; the service operates on a best-effort basis. The reviewed page
refers to a request-limit table but does not expose numeric endpoint limits in
its text; do not invent a guaranteed allowance. The proposed 20-minute shared
observation refresh remains subject to cadence/lifecycle verification.

The [CSCS terms page linked by MeteoSwiss](https://www.cscs.ch/information/terms-privacy-policy)
describes named CSCS websites and reserves third-party rights; it does not clearly
specify public object-store download quotas or MeteoSwiss dataset retention rules.
This is a scope ambiguity, not evidence that MeteoSwiss's CC BY dataset rights are
revoked. Keep the infrastructure gate open for Integration to identify the applicable
object-store policy. No new account, paid service or communication was initiated.

### Commands and retained evidence

`scripts/pollen_source_probe.py --output <new-proof-directory> --issue-time <UTC>
--station PBS --variable AMBRsnc --lead-hours 6` fetches explicit live public data.
Choose an available issue; the retained 2026-09-11 URLs will expire. The manifest
contains full hashes and request identities, not secret credentials or signed URLs.

Run `scripts/pollen_decode_proof.py --proof <retained-directory> --cosmo-root
<official-release-directory> --output <json>` offline using the pinned recipe
above; `--output -` emits JSON to stdout for read-only container mounts. Raw binaries are
retained locally in the task's sibling `pollen-proof-20260911` directory (9 files,
9,721,541 bytes); they are not committed to Git. Git contains the normalized proof
and full hashes. Reproduction on another host requires a lawful copy of those
retained bytes, or a new explicitly dated capture; upstream may no longer have them.
