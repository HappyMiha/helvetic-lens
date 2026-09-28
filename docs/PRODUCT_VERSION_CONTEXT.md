# Saved document context and exact source links — release 1.27

Status: DONE within the verified 1.27 scope. Scope MV2-002/020/024 was recorded before implementation.

The native comparison workspace now displays the full saved version identity,
file metadata, capture fingerprint, retained text counts and distinct capture
and declared-document dates. Report provenance opens each exact saved version;
passage links encode the complete version and passage identifiers. All five
native interface languages reuse their existing source-reading translations.

Pharma and the legal client expose the same metadata in document history and
the full saved-text reader. Progressive details keep the original filename,
revision and full SHA-256 available. Selected-article and synthetic-capture
limits remain visible. Unknown counts remain different from measured zero;
retained counts do not imply complete source coverage. Safe recorded HTTP(S)
source URLs remain usable; an absent source URL is explicitly labelled as a
monitored-page fallback, and unsafe recorded URLs are not silently replaced.

The Brandbook governs shared tokens, readable text width, typography and mobile
full-screen reading. Existing pinned-revision navigation, reload recovery,
original source language, retained AI excerpts and access checks remain active.
The legacy comparison resource/job-cache refactor is outside this slice.

## Verification

Implementation includes pure helper and actual server-rendered component tests
for five native locales, exact links, malformed metadata, original text escaping,
selection limits and unsafe URL rejection. Full gates, native API regression, builds, exact production assets and release
acceptance passed as recorded below.
No browser QA, private production records or paid provider probes are used.
The complete investigation and visual specifications remain IN PROGRESS.

### Local release validation — 28 September 2026

- All 412 native frontend cases, localization checks and TypeScript passed;
  the normal Next.js production build passed.
- Both product clients passed 154 tests, lint, strict TypeScript and the normal
  Sites production build. Shared reader and gateway implementations match.
- 104 distinct API/backlog cases passed across saved-history, comparison, public
  publication/reuse, guest access and rename coverage. After the owner confirmed
  Legal, all 13 rename cases and the backlog smoke were rerun against the final
  prefix (14 passed). The exact API Ruff gate passed.
- Rename journeys prove existing record identity, cross-alias idempotency and
  preview signatures, explicit publication/withdrawal, guest VIEWER/CONTRIBUTOR/
  EDITOR grants and revocation, cross-product/tenant denial and CSRF retention.
- Protected provider-value scans and whitespace checks passed; no new account,
  provider key, paid research request or private production record was used.
- Existing public repository identity and Apache-2.0 history were retained during
  rename. The Legal custom domain has active DNS/TLS on the existing Sites project.
  The old hostname remains active.

Exact source pushes and production activation are recorded below. Local validation
is not browser, human visual or professional acceptance.

## Verified production acceptance — 28 September 2026

DONE within release 1.27 scope. Native implementation
`50a18c2895b17ae442a047cc4826ea25733cd6ba` activated normally at 09:34:54 UTC.
Both existing Sites projects published exact source as version 30; Pharma
`8b77ce1e4181943e5cb1691975df7bed2ffc489a` and Legal
`675136ca28ddf953299febac2c1cdf06e46ebeb1` passed their exact GitHub CI runs.
All 136 packaged members per product matched the validated output.

Pharma passed 28 public route/auth/guide checks and 47 exact asset comparisons.
Legal passed 55 checks and 47 exact assets; every legal asset also matched on the
old hostname. Both API spellings preserve anonymous public reading and private
denial. The guide on both legal origins declares the new canonical URL.
The same GitHub repository identity, public visibility and Apache-2.0 licence
remain; the old GitHub URL resolves to the renamed repository. DNS/TLS is active
for both legal hostnames on the same Sites worker. The existing hourly automation
was updated in place and remains ACTIVE.

Native proof covers 48 exact web assets, 57 HTTP checks, five interface languages,
all nine navigation directions, 62 exact API modules, four healthy native runtimes,
five scheduler modules, unchanged migration `06d495bef125`, local Laya health and
the pinned local retrieval runtime using synthetic input. No private production
records or paid provider requests were used.

[Immutable release receipt](product-releases/2026-09-28-1.27.0.json) contains
source, deployment, artifact, CI and access evidence. The full investigation and
visual specifications and human/professional gates remain IN PROGRESS.
