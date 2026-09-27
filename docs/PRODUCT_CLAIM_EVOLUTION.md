# Evidence evolution across investigations

Release 1.15, scoped stage 4a. DONE within the scoped automated acceptance below. This does not complete
monitoring-triggered reopening, the full dynamic dossier spec or native visual migration.

After extraction, one durable comparison step may link up to 24 current claims
with at most 24 earlier source-supported claims from the same dossier/audience.
Public candidates must remain eligible within the same publication and publication
revision; private candidates exclude public research. Original extraction never
receives earlier claims as input. A single additional bounded model call receives
only the scoped existing statements and captured evidence. It can return only
existing claim IDs and relationship enums, never new source text, claims,
reasoning or externally supplied user explanations. This preserves independent
source extraction and avoids propagating withdrawn earlier text into new claims.
All input identities/revisions are rechecked before committing the comparison.
No extra provider or automatic public query is introduced.

A contained claim-change link references both exact ClaimEvidence records and the
previous claim/investigation through composite dossier/organization foreign keys.
The earlier statement, original citations and revision history remain unchanged.
Corroboration, contradiction and temporal update are machine-linked interpretations,
not independently verified facts. Both statements, sources and captured quotations
must be inspectable. Later-evidence status is a projection of currently visible,
active links; it must not silently overwrite the recorded claim status/history.

Current dossier editors may dismiss a false comparison or restore it with a reason,
a current revision and an idempotency key. Public review reasons are deliberately
public and require explicit consent. No new host membership or workspace authority
is granted. Native account/session checks and current guest roles remain mandatory.

Public link readers filter both source investigations before pagination/counts.
Withdrawal, contribution changes, source exclusion and account erasure must fence
candidate writes and remove derived public history/status. Archived private
comparisons stay in their own scope. Structured activity never stores earlier
private text or model reasoning; a refresh projects only currently eligible links.

Both products reuse the existing document/evidence layout, source typography,
Brandbook tokens, accessible controls and actual activity state. The native
monitoring integration is the next complete stage 4b; this slice establishes its
cross-investigation evidence history contract without claiming triggers exist.

## Delivered workflow and limits

Both client workspaces and anonymous public readers display **Changes over time**
with 20-item pagination, active/all filtering, exact paired quotations, source
hashes, capture dates and links back to the original investigations. Public server
rendering includes currently eligible comparisons without cookies. Readers poll
saved state every 15 seconds; failed access checks and changed public revisions
withhold cached comparisons. No poll launches research. The optical Lens comparison
state comes only from a recent persisted running step and expires after 95 seconds.

Comparison proposals are capped at 12 links. Input selection uses up to 24 claims
per side and the earliest supporting quotation per claim, with a bounded 90-second
model operation. This intentionally does not establish exhaustive coverage,
independent corroboration or correctness. Existing provider/search routes are
unchanged. An interrupted comparison is never automatically repeated; current
authorized participants can retry failed steps. Completed comparisons are retained
when another branch is retried; additional evidence can be compared by starting a
new investigation. Monitoring-triggered reopening is not implemented in this slice.

Review is serialized on the comparison row, checks the current dossier editor
role and optimistic revision, retains up to 100 decisions and supports exact
request replay. Public reasons require explicit publication consent. DTOs omit
user IDs, organizations, session bindings and request fingerprints. Private JSON
exports include eligible private comparisons, including dismissed history, within
the interactive export limit. Composite foreign keys cascade links when either
underlying investigation or exact supporting quotation disappears; author erasure retains other authors'
independently captured host evidence.

## Release acceptance

Implementation and exact native/both-client production acceptance are complete. Client checks: 95 cases per product, lint, TypeScript and production
builds passed. The 420-case broader native regression passed 419 cases and identified one old
queue test expecting two model calls. That fixture now explicitly accepts the
one bounded comparison step. After binding both exact supporting quotations,
all 100 affected native cases passed, including the 34 new comparison cases,
contribution queue/retry, public visibility, guest roles, migration/metadata,
account erasure and the exact Monitoring backlog gate. The exact API Ruff gate
passed. Exact activation and production receipts follow below. No browser interaction QA or real production
user records are part of these checks.

Validated client sources are Pharma `41884f2273436c8747fb6b6adaf868852575fa6d`
and Loyer `1552cb881f275c34633fd89f954eef639b0c0ca7`, saved as Sites version 18
in each existing project. Both builds contain 137 files; source and built output
were scanned against the three configured secret values with zero matches.
Both versions are now published at their existing public custom domains. Native
`git-2eb7d5ccc256` activated at 21:20:24 UTC on 27 September. Pharma and Loyer
published at 21:22:18 and 21:22:50 UTC respectively. Both exact-head GitHub CI
runs succeeded (36350878940 and 36350885909). Each production origin passed 90
HTTP/gateway/guide checks and 47 exact asset hash comparisons. All 42 checked
native modules match source; migration `01d495bef125`, both exact-quotation
composite foreign keys and current scope constraints are present. Three API/worker
checks, the stdin-only synthetic file parser and local Laya health passed.

[Exact release receipt](product-releases/2026-09-27-1.15.0.json) contains the source,
version, deployment and runtime evidence. Verification created no real production
user records or paid model probes. Browser interaction QA and independent
professional accuracy/human acceptance are not claimed. Stage 4a is DONE; stage 4b
monitoring-triggered reopening and both full specifications remain IN PROGRESS.
The existing hourly heartbeat remains ACTIVE.
