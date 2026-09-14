# Tender Today and Impact Inbox — active MV2-045/019/021 scope

Scope recorded before implementation, 14 September 2026: complete the missing
cross-monitor Tender entry on Today and Impact Inbox. Show the owner's saved new,
reopened and followed dossiers across profiles, current public publication summary,
review/previous decision, profile revision, explicit deadline status and exact
version links into the existing evidence/changes-since-review/decision workflow.
Inbox starts with pending review. Provide review/following filters, a Tender-only
pending count and stable bounded pagination; no inline bid from summary evidence.
All nine direction menus and existing source switches remain enabled.

Reuse current owner/workspace, embargo and durable public-source restriction
queries. Select bounded public summary projections only, never original payloads,
document bodies or private qualification/profile text for a feed card. Private
document/Q&A rights are rechecked by the existing exact reader. Hide excluded or
nonmatching discovery candidates unless deliberately followed; changed relevance
must remain visible for followed dossiers. Missing or withdrawn latest evidence
must not fall back to an old apparently current publication.

Dependencies: existing Tender projection, current restriction policy, immutable
versions and full dossier review. No provider keys, live collection, source rights,
email consent or external bid is needed to implement this reader. This is not
completion of authenticated documents/Q&A acquisition or semantic evaluation.

Acceptance: owner/tenant/viewer boundaries and no-store, source restriction and
embargo applied before page/count, no private original hydration or writes, equal-
time/replaced-anchor pagination, filters/count parity, retained previous decision
on material reopen, five languages/mobile/keyboard, exact version navigation,
failure/permission/page-return redaction, existing Tender review and Today legacy
regression. Required API Ruff/build/format/backlog gates; complete commit then
immediate push main. Actual release and human/provider acceptance stay separate.

## Implemented behavior and evidence — 14 September 2026

Today and `/impact` now include the owner-private tender queue; all nine active
directions have a Today integration. The new GET `/api/tender-watch/today` reads
latest versions across saved profiles with all/pending/new/reopened/reviewed and
following filters. It applies current membership, both organization boundaries,
owner, archive, publication time and current public-source restriction predicates
before counting/paging. Nonmatching unfollowed discoveries are excluded; followed
dossiers remain visible when their relevance changes. Restricted latest evidence
does not fall back to an old publication.

Only the bounded public summary and private dossier metadata are selected. A
first page uses three SELECTs and does not hydrate original snapshots, material
sections, matching/profile details or document content. The exact linked reader
continues to enforce full source integrity and current private document rights.
The pending count covers this owner's permitted tender queue and following scope;
it is not a global all-domain unread count. Immutable version observation time/id
form the cursor, even after the anchor dossier is reviewed or receives a newer
revision. Default page size is 20, maximum 50. No new mutation, collection, AI,
email, source approval or submission route is added.

Five-language cards show source-language titles, SIMAP's required notice,
deadline in Europe/Zurich with an explicit unknown state, recorded time, profile
revision, project-versus-lot qualification limits and a retained prior decision
when a material revision reopens review. Cards link to the exact dossier/version
and existing accumulated-changes/decision journey. Owner/workspace/role changes
and page return remount private data; errors and revoked access clear the queue,
with retry, focus/minute refresh and previous/next paging. Viewers can inspect
their own queue; decisions remain behind existing owner/role/CSRF/version checks.

Verification on the feature's introducing commit:

- **38 tests passed** across Tender Today, repository, current source rights and
  HTTP workflow. Real saved publications exercise decision/reopen/exact evidence,
  source withdrawal/embargo before count, excluded/followed relevance, old profile,
  53 equal-time versions across profiles with a replaced anchor, private owner/
  tenant and viewer boundaries, SELECT-only projections, no-store and CSRF.
- Required `ruff check services/api deploy/release_manager.py` and changed reader,
  copy and guide Prettier checks passed. Root isolated build `tender-today` passed
  lint/types/translation/navigation/help gates. Generated build-path changes were
  reviewed and removed after terminal build completion.
- New built-product browser checks passed **eight full-document axe checkpoints**,
  five locales/mobile geometry, required source notice, pending/following filters,
  paging, keyboard reload, exact-version navigation, viewer, errors and access/
  page-return redaction. No Tender mutation occurred in this journey.
- Existing full Tender browser regression passed **36 full-document axe
  checkpoints**, profile/save/start, public context, follow/internal decisions,
  material reopen, originals/documents/changes reader, error recovery, lifecycle,
  five languages/mobile and viewer/source gates. Tests use synthetic responses.
  All reported axe violation severities and prohibited ARIA checks passed;
  incomplete/manual accessibility checks are not a certification.
- Existing main interest-feed browser regression passed **ten journeys** across
  five locales at 390/1440px: legal cards, exact evidence/permalinks, private
  reading state, paginated topics/watches, filtering and error/cursor recovery.
  The mandatory final backlog consistency/customs-deferral test passed.

Reviewer: the implementing single agent. Independent native-language review,
real user testing and live source acceptance remain open. This completes the
scoped queue/navigation journey, not broader cross-domain card aggregation,
shared company ownership, semantic evaluation or authenticated live documents/
Q&A acquisition. MV2-045/019/021 remain IN PROGRESS. No production consent,
credentials or source approvals changed. Verify actual release separately from push.
