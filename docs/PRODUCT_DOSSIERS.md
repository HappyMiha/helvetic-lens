# Pharma and Loyer monitoring dossiers

Status: DONE for the scoped product implementation and production publication,
verified on 26 September 2026. Broader MV2 and professional pilot acceptance remain separate.

Two dedicated Apache-2.0 clients share this platform's identity, organization access,
source catalogue, topic matching, AI adapters, durable jobs, notifications and evidence
volume. Dossier lists are scoped by organization and product. Drafts stay author-private;
activated dossiers are visible to the current organization. Existing role boundaries
remain authoritative; viewers read and download, administrators edit and invite.
Native profiles remain accessible to authorized members through the full platform.

## Workflow and persistence

The five-step workflow from H26-07 is retained. Product dossier creation saves a native
profile and its wrapper in one transaction. Client retries reuse the same dossier.
Source recommendations use the actual catalogue and reject model-invented source IDs.
AI availability is independent of manual configuration. Activation keeps the native
source-pack, matching, subscription, consent and verified-email gates.

Dossier entries include original-source references, comments, relevance decisions,
files and AI refinement proposals. Entries carry authors and timestamps. File downloads
require current membership and dossier visibility; filenames never control storage paths.
Uploads are bounded to 10 MB, 50 files per dossier and 500 MB per organization. SHA-256
fingerprints accompany metadata. Files remain in the existing backed-up evidence volume;
retention preserves referenced files and account erasure includes private file inventory.
Shared records follow existing retained-work and detached-author rules.

Connecting an individual page uses the native public-network-safe fetcher, stores a real
baseline and enables its daily DocumentWatch with an actual next_auto_check_at. The normal
scheduler admits it to the durable scan queue. Repeated connection does not duplicate a
watch. This monitors a selected page, not the whole domain, and native fetching failures
remain visible. Pausing topic matching leaves separately configured shared page watches
and source collection unchanged; the client states this explicitly.

Saved relevance feedback is bounded context for a real call to the organization's selected
AI provider. Proposals retain model/provider, feedback references and captured topic
revisions. Applying one requires human selection and creates the native revision, backfill
job and dossier review record together. Stale/cross-dossier topic changes are refused.
Repeated acceptance is idempotent and a different choice cannot masquerade as the same
application. Source rights, source freshness and professional interpretation remain separate.

## Verification

- Exact API lint: `ruff check services/api deploy/release_manager.py` passed.
- New product dossier suite: eight cases covering durable retries, notes/export,
  cross-product and cross-organization reads, file ownership/integrity/CSRF, author-private
  drafts, viewer denial, actual model feedback input, reviewed native revisions, stale
  proposal rejection, native daily scheduler admission/deduplication, bounded catalogue
  recommendations, attachment retention and account erasure inventory.
- Final affected product/document-monitoring/maintenance run: 19 passed.
- Existing legal-profile, topic, account-erasure and backlog regressions: 32 passed in
  the preceding affected run. Initial failures in two new model test doubles were fixed;
  the final product suite passes with explicit scripted proposal responses.
- Frontend clients have strict contracts, TypeScript/lint/build gates and five gateway
  contract tests per product for cookie filtering/forwarding, route and mutation-origin
  checks, streamed upload bounds, private binary responses and visible upstream failure.
- The normal production release also passed 755 tests (96 smoke, 659 functional),
  exact API lint, backup, migration/startup and public health verification. Its separately
  configured integration suite was skipped by the existing release policy.
- No test client records were seeded into the production database. Authenticated
  workflow/privacy evidence comes from the native tests; production checks below use
  anonymous HTTP requests. Browser interaction and professional usefulness acceptance
  are not claimed by this release record.

## Deployment contract

Client repositories: HappyMiha/helveticlens-pharma and HappyMiha/helveticlens-loyer.
Production hosts: pharma.helveticlens.ch and loyer.helveticlens.ch. The original
helveticlens.ch deployment remains the shared core. No retired Monitoring deployment
is recreated, and existing private data, credentials and source approvals are preserved.
The owner explicitly authorized these additional product sites on 26 September 2026.

## Confirmed publication

| Product | Public Apache-2.0 repository | Production | Validated source |
|---|---|---|---|
| Pharma | [helveticlens-pharma](https://github.com/HappyMiha/helveticlens-pharma) | [pharma.helveticlens.ch](https://pharma.helveticlens.ch) | `36c778deab0b71a4f52654462f1bcedc0bd8ddf2` |
| Loyer | [helveticlens-loyer](https://github.com/HappyMiha/helveticlens-loyer) | [loyer.helveticlens.ch](https://loyer.helveticlens.ch) | `74f2d7b464cd86ab1fa3c33e52ade15e49a9be8e` |

The shared core deployed `a34269fc87b14873bd25ffc9341c00fa3bb427d6`
(`git-a34269fc87b1`) at 20:37:29 UTC on 26 September 2026. Both independent
client builds passed local tests, lint, TypeScript and production builds. Their
[Pharma CI](https://github.com/HappyMiha/helveticlens-pharma/actions/runs/36270220064)
and [Loyer CI](https://github.com/HappyMiha/helveticlens-loyer/actions/runs/36270225118)
also completed successfully. GitHub reports both repositories PUBLIC and Apache-2.0.

Both Sites deployments succeeded. Custom hostnames and SSL certificates report active.
On each requested HTTPS hostname, the product page returned 200 with its correct title;
four linked CSS/JavaScript assets returned 200; `/api/auth/session` returned 200 and an
unauthenticated identity; its own private dossier route returned 401 and `private,
no-store`; the other product's route returned 404; a cross-origin login mutation was
refused with 403 by the product gateway before reaching the core. CNAME and validation
records were added only for the two requested subdomains; the apex and mail DNS were
not changed.

Operational boundaries: the clients currently use English, share the existing organization
and personal email digest, and require sign-in for private work. Source page watches are
individual URLs rather than whole-domain coverage. Source availability and configured
AI/email providers keep their native readiness gates. Saved AI improvements require
review and explicit acceptance before changing topic revisions.
