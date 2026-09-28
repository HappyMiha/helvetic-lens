# Helvetic Lens Legal rename — release 1.27

Status: DONE within the verified 1.27 scope. Owner-requested scope addition on 28 September 2026,
recorded before implementation. The owner confirmed Legal after reviewing naming alternatives. The new public name is **Helvetic Lens Legal**,
the primary origin is **https://legal.helveticlens.ch**, and the existing public
repository will be renamed to **HappyMiha/helveticlens-legal**.

## Outcome and compatibility

- Update product branding, metadata, guides, repository links and cross-product
  navigation in both clients and the shared native platform.
- Reuse the existing legal Sites project, its public audience and all existing
  dossiers. Add the new domain; retain the former hostname as a working alias.
- Expose `/api/products/legal` through the same authorization, CSRF, tenant,
  publication and guest-access pipeline as the existing legal product.
- Keep `loyer` as an internal historical storage key and supported API alias.
  This is a rename of the existing product, not a database copy or new tenant.
  Existing IDs, source snapshots, invitation tokens and publication signatures
  remain valid. New public source links use the Legal hostname.
- Update the existing repository, local product directory, Sites display title
  and active hourly automation. Keep opaque project/automation identifiers and
  historical release receipts unchanged. Do not rewrite supplied specifications
  or the original Brandbook; this owner decision supersedes their old spelling.

## Acceptance

Both API spellings must address the same records and preserve idempotency,
author-selected publication, anonymous public reading, private denial, CSRF,
cross-product isolation and dossier roles. Gateways must reject both legal
spellings in Pharma. Exact validated assets must serve from the new and old
legal origins; the new GitHub repository and existing Sites project must retain
their original identities. Frontend tests, API tests, builds, main pushes and production
evidence passed as recorded below. Human visual and professional acceptance are not claimed.

Host-scoped sign-in and appearance preferences do not transfer between domains.
The existing domain remains available to preserve an open signed-in workspace;
the primary domain uses its own normal sign-in. No cookies or private browser
state are copied across origins.

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
