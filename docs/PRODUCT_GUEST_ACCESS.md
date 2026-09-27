# Dossier-only guests — release 1.13

Status: local acceptance passed; exact production acceptance pending.

An owner can invite an existing account by its verified email address to one
managed Pharma or Loyer dossier. The account accepts a seven-day invitation as a
Viewer, Contributor or Editor, then finds the dossier in Shared with you. Drafts
and activated dossiers use the same role checks, evidence readers and durable
investigation coordinator. A copied link never grants another account access.
No invitation email, native organization membership or session switch is created.

## Authority and retention

The host workspace keeps ownership, public publication, monitoring setup and
source administration. Guests cannot become owners, even if they later acquire a
native workspace role. Guest editors can review evidence, work on questions and
start/control research; contributors can add material and analyse their own
contributions. Assignment choices are limited to host administrators already on
the dossier team or explicitly referenced in its work. Native personal feeds,
workspace searches and digest preferences stay in the login workspace.

Original files, linked saved-document history, captured investigation evidence,
matched topic evidence, exports and activity are read through the dossier scope.
Unlinked documents and sibling dossiers remain inaccessible. Removing the guest
grant closes future access; downloads and already received copies cannot be
recalled. Native account erasure removes the guest's grants/invitations without
erasing the host dossier. Existing native membership removal still cascades to
native dossier grants. Last-owner protection remains in force.

## Implementation boundary

Only an exact dossier route with a current accepted guest membership can select
the dossier's organization. The only pre-acceptance exception is the exact
account-bound invitation acceptance route. Every operation rechecks the record
and capability; scope selection is not an authorization cache. Global/native
routes never receive the host context. Cross-organization personal directory and
inbox queries always filter the authenticated recipient, product and guest scope
before counting and paging. Registered verified accounts are looked up only by
exact normalized email; there is no public account directory or account creation.

Migration `fec495bef124` preserves each dossier/organization composite foreign
key. Native grants retain a nullable binding to the real native membership;
checks require it for non-guests, forbid it for guests and forbid guest ownership.
All existing rows are backfilled as native. Downgrade refuses retained guest
memberships or invitations rather than silently reinterpreting their rights.

Investigations persist the original login organization separately from the host
dossier organization. HTTP and worker checks validate current user, session,
original login organization, native membership and current dossier role before
and after external work. Session revocation, source-workspace changes or removed
grants pause work and discard late claims. Resuming captures the current valid
session again. Legacy investigations retain their original organization binding.

## Scope still open

Inviting unregistered users, automatic invitation delivery, guest subscriptions,
living public dossiers/slugs, recurring open-web research, semantic private-file
indexing, cross-investigation reconciliation and material-change reopening remain
separate outcomes. Full dynamic-dossier and native visual specifications remain
IN PROGRESS. Brandbook v1.0 now governs both client shells; it does not mark the
broader native visual migration complete.


## Local acceptance

370 distinct native cases pass: 368 affected authentication, product, research,
team/privacy, account lifecycle, migration and backlog cases, plus two guest live
activity/native-viewer journeys. The two existing provenance fault-injection
fixtures now forward the explicit dossier argument while retaining their role
and session revocation assertions. Focused guest/member/private monitoring and
research/work acceptance also passes (50 cases, overlapping the broad run).

Both clients pass 85 tests, lint, strict types and production builds. The final
archives contain 121 files each and none of the three configured provider keys.
Seven text/background pairs exceed 4.5:1. The supplied brandbook Markdown is
unchanged (SHA-256 `5cde494278854f7190a33ae8b11742c61149904225e337463a17c66e53e0b006`).
PDF pages were visually inspected; client browser/human visual acceptance is not
claimed by this background cycle. Site versions are saved; production acceptance
will be recorded only after the new native policy and both sites are active.
