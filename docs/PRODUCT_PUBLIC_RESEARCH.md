# Living public dossier research

Release 1.14, scoped stage 3. The scoped implementation and exact production
acceptance are DONE; activation evidence is recorded below. The complete dynamic-dossier and
visual-language specifications remain IN PROGRESS.

## Public author choice

An owner enables living research in the existing signed publication preview.
The preview binds the exact text, links, revision and new mode to the account and
session. Old published snapshots remain snapshots. A stable Unicode title-based
slug is generated once, with the publication UUID as its collision-free suffix;
renaming does not change that URL. Existing UUID links still work.

Living public dossiers use the existing native Investigation/Plan/Branch/Source/
Claim/Entity/Event records and worker, not a second research pipeline. Every public
run additionally binds one exact published revision and one exact, deliberately
public contribution revision. Composite foreign keys bind the publication,
contribution, dossier and organization. A database check forbids mixing a private
entry trigger with public research. Migration `ffc495bef124` leaves legacy runs
private and refuses downgrade while public research or originals are retained.

## What is researched

Verified accounts can submit a comment, URL, correction, research question or
supported original file under an explicitly entered public name. Confirmation
discloses both publication and automatic public analysis. Research questions also
require explicit disclosure of external discovery. Ordinary comments/files do not
become search queries. Only the disclosed question and exact entity names found
in permitted public sources can extend external discovery.

The seed contains the current published summary/body and that contribution's
text, source links and original. It never invokes private `research_sources` or
reads private parent entries, profiles, files or other investigations as context.
Public submissions remain candidate evidence; extracted claims retain exact
quotes, locators, source hashes, attributed originals, uncertainty and history.
Source support is not independent verification. The existing Jev/Laya decision
interface and configured analysis model are reused with their existing bounds.

Public originals accept matching TXT, Markdown, CSV, HTML or text PDF, up to 2 MB.
Native isolated extraction retains its CPU/memory/time/page/text limits. Downloads
check current publication/contribution visibility and the exact original hash,
then serve bytes as an attachment with `nosniff` and a sandbox CSP. No inline HTML
or guessed OCR capability is introduced. Fifty retained public files per dossier
and the combined 500 MB workspace attachment limit bound storage. Public work is
also limited to 30 submissions per account/dossier/day and the existing shared
search/model/branch budgets. No external malware scanning capability is claimed.

## Identity, revocation and moderation

Outside participants retain their own native sessions and workspace memberships;
public participation grants no host membership or private access. Jobs/outbox are
explicitly assigned the host dossier organization, separately from the initiating
login organization. Current active/verified user, native membership and exact
session binding are checked before and after network work. Authors control their
own research; current dossier editors can control it through the same durable
pause/resume/cancel/retry actions. Moderation remains available through native
public discussion controls, with current dossier editor support.

Anonymous SQL readers apply consent/revision/visibility/source-exclusion gates
before counts, pagination and typed search. The SSE reader rechecks them for
every batch. Withdrawal, contribution revision/moderation and erasure remove
affected research; queued/in-flight results cannot promote newly hidden material.
Current excluded sources withhold the whole affected public investigation, so
claims, entities and historical quotes cannot leak through an alternate reader.
An explicit publication edit establishes a new public research revision. Older
derived work remains retained privately and is never silently republished.
Restoring a discussion contribution does not silently restart research; its author
can submit a reviewed edit. Already downloaded or independently copied public
material cannot be recalled. Removing a public file erases its online original;
account erasure also traverses public originals and derived research while
retaining a different owner's host dossier/publication. Unique public originals are
unlinked after the database erasure commits. Filesystem failures retain the existing
orphan-retention retry policy; scheduled cleanup preserves every retained public
original, including hidden contributions. Other shared artifact namespaces retain
their existing reference-aware retention policy.

## Reader and search

Both clients use the shared evidence/source/Lens/transparency components, one
public Ask form, discussion/file composer and structured live activity. The
global Ask bar can prepare a public question, followed by explicit author and
publication consent. Anonymous server rendering contains public data only.
Stable links select an investigation and anchor a claim, entity or source.

The anonymous public-knowledge endpoint distinguishes DOSSIER, CLAIM, ENTITY,
SOURCE and INVESTIGATION. It performs escaped literal word matching in the
published projection and eligible research ledger, without private queries,
provider calls or a fabricated semantic/vector index. Global Ask and the public
directory use this reader. Exact evidence-derived results remain distinct from
the existing multilingual hybrid open-web discovery workflow.

## Remaining full-spec work

Cross-investigation claim reconciliation, monitoring-driven material-change
reopening, recurring open-web discovery, private semantic indexing, independent
professional quality evaluation and native-platform visual migration remain open.
No complete-spec or exhaustive-internet-coverage claim is made by this release.

## Local acceptance — 27 September 2026

Both clients pass 89 tests, lint, strict types and final portable Sites builds.
The broad native run passed 386 tests and found three failures: two migration-head
assertions and physical public-original erasure. All three were corrected, and
the subsequent 39-test focused run passed, including all 19 public-research cases,
the two migration cases, account erasure and existing maintenance. The two-test
final gate also passes filesystem failure/retry and the required backlog inventory.
The exact API lint gate passes. All 137 built files per client were scanned against
the three configured provider key values, with no matches.

Native fixtures execute actual HTTP/session/database/job/parser flows with
controlled external services: cross-workspace participants, both products, exact
public-only context, attributed quotes, claim history, evidence-based replanning,
signed opt-in, source exclusions, session/membership/workspace revocation during
network work, public moderation/withdrawal/edit/republish, upload limits and hash
integrity, explicit host job scope and real account erasure preserving its host.
No authenticated production record or paid research probe is required. Browser
interaction, whole-page accessibility and independent professional accuracy are
not claimed by these automated gates.

## Exact production acceptance — 27 September 2026

Native functional main `d54511e8e06c3fcc9ed9ee038cab5c4d0931856c` activated at
20:14:25 UTC. Migration `ffc495bef124`, all 40 checked native module hashes,
public/private/team/guest/contribution constraints and research tables match;
three worker checks, the isolated local parser fixture and local Laya pass.

Both existing public Sites published version 17 successfully: Pharma main
`4b9c8ad92263424218df3389bdfdb799f309f470` at 20:16:22 UTC and Loyer main
`1664781fa1f479423ebc5cb0549b54fed608ac91` at 20:17:04 UTC. Each custom
domain passes 80 anonymous HTTP/auth/gateway/reader checks and all 47 exact
served JS/CSS/favicon hashes. Both GitHub client CI runs succeeded (36347009248
and 36347020945). The existing hourly heartbeat remains ACTIVE.

[Exact release receipt](product-releases/2026-09-27-1.14.0.json). This completes
scoped public research stage 3; the complete dynamic-dossier and visual-language
specifications remain IN PROGRESS with the remaining outcomes listed above.
