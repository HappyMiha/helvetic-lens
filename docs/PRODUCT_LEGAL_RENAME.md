# Helvetic Lens Legal rename — release 1.27

Status: IN PROGRESS. Owner-requested scope addition on 28 September 2026,
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
their original identities. Frontend tests, API tests, builds, push and production
evidence are pending. Human visual and professional acceptance are not claimed.

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

Source pushes and exact production activation remain to be recorded; this local
validation is not browser, human visual or professional acceptance.
