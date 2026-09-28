# Source reading and inspectable provenance

Status: VERIFYING — scoped release 1.25 under MV2-002/020/024. Scope, source readiness,
dependencies and acceptance were recorded before code. Full dynamic/visual
specifications and the broader MV2 tasks remain IN PROGRESS.

The native saved and corpus readers separate source origin, capture time, stated
document date and unknown primary/secondary classification. Actual retained
passage/character counts are prominent; unavailable values remain different from
measured zero. Saved-source details disclose the existing version, file name,
format, language and recorded SHA-256 fingerprint. The existing bounded authorized
SQL projection now includes its stored content_hash scalar; it does not hydrate
a full version, add a second request, alter permissions or introduce a schema.

Both product readers show actual retained-excerpt counts and unique claim usage,
with inspectable source version/fingerprint and preserved quotations. Capture time
never becomes publication time. Empty captures, unavailable fingerprints and
unknown classification remain explicit. Source URLs must remain HTTPS without
user information in the products; the native reader retains legacy HTTP(S)
support while rejecting unsafe or credential-bearing references.

Brandbook typography, 60–75-character reading measure, neutral theme tokens,
progressive details and restrained framing guide all three readers. Existing
Radix/Base UI primitives, keyboard focus, exact passage/PDF/source anchors,
downloads, registry return, paginated large documents, synthetic/import notices,
language, authority and private drafts remain intact. No decorative Lens or
truth/completeness score is added. Five native locale dictionaries cover new copy.

## Verification and limits

The full native frontend/localization/typecheck tree passes 391 cases, including
11 new source-reader behavior and actual server-rendering cases. Both products
pass 142 tests each (seven new), lint and strict types. Native Next and both
portable Sites production builds pass. The exact API Ruff gate and 55 affected
API cases pass, including large paginated documents, exact targets, capture
fingerprints, source access withdrawal, document history and the backlog smoke.
Production activation and exact origin/runtime verification remain pending. Focused
behavior checks cover real rendered metadata, untrusted text, safe URLs, unknown
versus zero, honest capture limits and exact claim/source destinations. Backend
large-page and withdrawal cases check fingerprint identity without full ORM loads.
No production private records, paid research requests, new accounts/keys or
outgoing messages are used. Browser/human visual, language and professional
acceptance remains open; no browser view is opened for this background cycle.
