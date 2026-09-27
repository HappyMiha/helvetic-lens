# Private dossier contributions

Status: VERIFYING (implementation and local acceptance complete; exact deployment pending). Dynamic dossier stage 2a; the full specification remains open.

## Scope and boundaries

Both product clients get one contribution composer: comment, HTTPS source URL,
correction, research request or file. Submission retains the original DossierEntry
and artifact and queues its own native investigation atomically. Original author
and submitted text are never rewritten by extraction. Current native workspace
administrator write/viewer read and private-draft boundaries remain authoritative.

Only the submitted URL is fetched through the existing public reader. Its passage
ranking uses a fixed public purpose, never the private comment, title, goal or file.
These investigations cannot search the public web or expand entities into external
queries. Private material is analysed by the configured workspace model. The usual
explicit Ask workflow remains available for deliberate public discovery.

One active investigation per dossier executes at a time. Later contributions queue,
with visible saved status, without losing the original or spending on duplicates.
Failed source/analysis steps can be explicitly retried; completed evidence remains.
Legacy save-only requests keep their existing default. No automatic publication,
email, source approval, membership change or cross-run claim reconciliation.

## Acceptance to verify

- Current session, organization, membership, dossier and CSRF checks; same-key retry
  returns the same original and job, a changed body/author cannot reuse that key.
- Uploaded original bytes/name/hash/download survive parser and model failures.
  Format and size validation, bounded local subprocess extraction and explicit
  unsupported/scanned/encrypted/time-limit outcomes; no fabricated OCR.
- Citation quotes match retained passages; page/character locators and originals
  remain inspectable, with human author attribution separate from model findings.
- Private text cannot reach discovery/ranking queries, including follow-up entity
  branches; source exclusions and revocation/cancel races discard late results.
- Queued work, retry, recovery, schema preservation, both client gates and exact
  native/Sites production activation have English evidence before scoped DONE.

## Implementation and local acceptance — 27 September 2026

Migration `fbc495bef124` adds a unique contained contribution origin and an explicit
external-discovery flag to native investigations. The original entry, run and
outbox commit together. Exact repeated submissions recover the same original and
job; changed author, content, file bytes or analysis choice conflict. Legacy
save-only submissions retain that behavior. Stored authorship remains on the
original entry; account erasure uses existing native actor anonymization.

Queued reviews serialize per dossier without consuming failure attempts. Existing
session/membership/draft checks, generation fencing, current source exclusions,
worker recovery and access-checked SSE remain authoritative. Human text, URL
captures and uploads have distinct source kinds. Quotes must match a retained
passage exactly. Contribution reviews have no public-search branches; URL passage
ranking uses a fixed public purpose and a neutral title, never private material.

File bytes stay in native artifact storage and download as private attachments.
A fresh local parser subprocess enforces a 512 MB address-space limit, 12 CPU
seconds and a 25-second wall deadline, with kill/reap on cancellation. It validates
extension/content-type and UTF-8 or PDF input, accepts up to 2 MB for extraction,
reads at most 60 PDF pages, text from the first 20 and 24,000 characters. Original
uploads retain their existing 10 MB/50 files/500 MB workspace storage limits.
Unsupported, scanned, encrypted, oversized or damaged inputs remain downloadable.
No OCR or malware-scanning service is attached; file bytes are never executed.

Explicit retry preserves source captures, successful extraction indices and all
activity/history, then revisits only unavailable indices. Interrupted in-flight
work is not silently repeated. Corrections/research requests can inspect two
bounded saved snapshots; cross-investigation claim reconciliation stays open.

Validation: 324 broad affected native tests passed (3 smoke, 321 integration).
A final 46-test run passed after tightening source-exclusion handling, including
20 new contribution cases: actual TXT/HTML/PDF subprocess extraction and original
downloads, MIME/scanned/size failures, source exclusion before and during reading,
private URL/query boundaries, exact quotes and retained authorship, idempotency,
serialized queues, partial retry, cancellation/revocation/interruption and SQLite
migration preservation/metadata equivalence. Exact API Ruff gate passes. Both
clients pass 80 tests, lint, strict types and production builds. New client SSR
checks prove explicit disclosure/submission, read-only controls, escaped original
text and contained download links. Each build has 121 files with no configured
provider-key values. No browser interaction or independent professional-quality
acceptance is claimed. Production verification is recorded separately.
