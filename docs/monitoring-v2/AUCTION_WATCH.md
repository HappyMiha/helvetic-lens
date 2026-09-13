# Auction Watch — B8

Status: IN PROGRESS, 13 September 2026. Scope: MV2-049/050 and auction-specific
contributions to MV2-043/044. Nine active directions remain; C4 stays deferred.
The previous integrated Monitoring implementation was pushed to main as
4859c58a8b255b40e30a6c2ae00d363e72f0d9dc. Auctions is the next complete direction.

## Required outcome

Private asset profile → official auction discovery → explained category/location/
keyword/brand/budget match → follow individual auction or lot → internal
Inspect/Bid/No-bid/Monitor → material price/deadline/conditions/cancellation change
→ reopened review → Today/Inbox and separately consented delivery. Preserve all
AC-B8-01…12 in the practical specification. Bid is only an internal decision.
No bidding, auction registration, payment or contact with sellers is included.

Auction and lot identities remain distinct. Current bid, starting price, minimum
price and estimate retain their types; UNKNOWN is never zero. An explicit
CHF 8,500→12,700 current-bid change crosses a CHF 12,000 profile limit once;
further increments do not repeatedly notify without opt-in. Unknown gaps do not
prove a crossing. End-time changes invalidate old reminders; cancellation and
unknown deadlines suppress them. Keep current state and immutable versions.
Document absence on an incomplete/failed listing is not removal. Another canton
must pass the same adapter conformance cases without changing domain rules.

Reuse the current private ownership/membership/CSRF, immutable configuration,
source rights/retention, document-set comparison, durable jobs and consented
outbox boundaries. All new section switches will default enabled in production,
as requested, with missing source access and unsupported coverage shown explicitly.

## Source investigation — 13 September 2026

The [official Aste UEF listing](https://www.aste.ti.ch/it/) is publicly readable.
[Lot 185](https://www.aste.ti.ch/it/auction/185) distinguishes starting price,
bid count, minimum increment, start/end times and linked documents. A zero-bid
starting price must not be normalized as a current bid. An older crawler render
still describes bidding as not started; that is not evidence of current status.

[eGant sale conditions](https://www.aste.ti.ch/it/condizioni_generali), dated
9 April 2026, cover participation and sales. The inspected text does not establish
a public API or automated republication permission. [Official contact](https://www.aste.ti.ch/it/contatto)
is available; no inquiry or registration was sent. Separate official property
auction notices exist, but current category coverage and a supported native
acquisition contract remain unverified. Public visibility does not close MV2-049.

Firecrawl CLI was available but its verification request returned insufficient
credits. Official pages were inspected with the available web reader instead;
no subscription, source account, bid or authenticated request was created.

## Verification plan

Test typed-price unknowns, explained filters, stable auction/lot separation,
new/changed/cancelled/postponed/relisted records, low-noise price thresholds,
stale/unknown source state, reminder recalculation, document gaps, source rights
and parser drift. Test private CRUD/history, member revocation, review conflicts,
current-version consented delivery and a second-canton adapter fixture. Complete
five-language desktop/mobile browser journeys, required build/lint/migration
checks and recorded source/release/human acceptance. No DONE claim yet.

## Private profiles and deterministic rules — 13 September, 21:08 UTC

The enabled `/auction-watch` section now provides owner-private create/edit,
configuration history, archive and confirmed delete. Profiles retain categories,
canton, explicit location/keyword/brand phrases, an exact CHF budget with a
selected price type, and future material/ending-soon preferences. Saving a profile
does not start ingestion or grant email consent. Unknown source coverage is
shown in all five product languages, with a direct official-source link.

The authenticated API uses normal session/CSRF and membership checks, a shared
60/minute rate bucket, private no-store responses, idempotent creates, revision
conflicts and bounded lists/history. Migration `6fac2d70ed61` adds private monitors
and configuration revisions after `5efb1c69dc50`; organization-consistent foreign
keys and the central ownership policy include both tables. Monitoring Centre
now opens all nine directions when their implemented feature switches are enabled.
IP and Auction cards display their own source attribution instead of falling
through to the Air source label.

Domain rules retain distinct auction/lot identities and typed prices, explain
known matches/exclusions/unknowns, suppress repeated bid increments by default,
detect a proven above-budget crossing and recalculate ending-soon eligibility.
Incomplete document listings cannot prove removal. Reminder eligibility rejects
stale/future observations, non-open/cancelled auctions and unknown/past deadlines.
These are stateless rules, not a durable collector, review queue or delivery job.
The second-canton fixture verifies domain equivalence only; native adapter
conformance and live rollout remain open.

Verification: 34 rule/backlog checks passed (0.34 s); 36 rule/API checks passed
(7.91 s). After the final migration-retention assertion and Centre integration,
30 API/Compose/Centre/trademark-regression/backlog checks passed (50.95 s).
The root frontend production build passed. Three browser-reader tests passed for
exact money entry, independent profile defaults and five-language copy. The
synthetic headless browser passed 17 workflow/accessibility checkpoints including
create/edit/history, exact CHF 12,000.50 storage, conflict preservation, archive/
delete, viewer restrictions and membership-denial redaction. Desktop/mobile axe
reported zero violations; images were visually inspected. Existing incomplete
Marvin contrast checks are not counted as passed manual accessibility review.

Official current acquisition and rights, source-state persistence, private auction
discovery/following/review, Today/Inbox, durable reminder generations and actual
consented delivery remain required. MV2-049/050 remain IN PROGRESS. This publishes
the usable profile-management outcome and ninth navigable section, not completed
B8 acceptance or live auction monitoring.

## Private source-backed tracking — 14 September 2026

The profile now supports start/resume against a fresh reviewed source, scheduled
projection of retained source records, pause, explained private results, following
individual lots, internal Inspect/Considering a bid/No bid/Monitor decisions and
paged source-version history. A material change reopens review while retaining
the earlier decision. The user can stop following and pause after source access
is lost. All five languages expose this workflow in the enabled Auction section.
The interface describes source readiness inside the section; it does not hide it.

Migrations `70bd3e81fe72` and `81ce4f920a83` add the shared permission-scoped
source journal and organization-scoped private tracking tables. Reviewed policies
bind source identity, HTTPS subtree, permitted purposes, canton/category scope,
freshness and retention. Admission verifies evidence hashes, record identity,
generation and cursor; request replay is idempotent. Current heads and immutable
versions distinguish evidence refresh from changed facts. Revocation/expiry
redacts reads immediately; an independent cleanup job removes retained payloads.
Private decisions and events retain references and codes, not duplicate licensed
payloads. No live permission, source account or source write endpoint was created.

The bounded scheduler projects only retained permitted records. It resumes source
pages, rejects stale review submissions and pauses when ownership membership is
revoked. Intermediate price/deadline revisions are considered between polls:
CHF 8,500 → 12,700 reopens a CHF 12,000 review once, while subsequent ordinary bid
increments remain quiet. A deadline changed away and back has distinct reminder
generations. Unknown price remains unknown; incomplete source pages never imply
cancellation. Coverage is explicitly unverified, even with readable records.

Verification: 64 combined workflow/API/source/Centre tests passed in 70.70 s,
including migration metadata and downgrade/upgrade preservation, private ownership,
revocation, replay, price crossing, deadline generations and version-history
retention. Exact API Ruff passed. The root isolated frontend build passed; changed
frontend files pass Prettier and the patch passes whitespace checks. The synthetic
browser passed 16 tracking checkpoints and the existing 17 profile checkpoints.
Both desktop/mobile axe runs reported zero violations; tracking screenshots were
visually inspected. Synthetic fixtures do not prove native source access or live
auction behavior; incomplete manual accessibility checks remain unverified.

This publishes a usable private tracking outcome for reviewed journal records.
Native acquisition/current official reuse and category evidence, Today/Inbox,
durable ending-soon delivery, separately consented email and real-user acceptance
remain open. Notification preferences are retained but no delivery is claimed.
MV2-049/050 remain IN PROGRESS; AC-B8-01…12 are not complete.

## Today, Inbox and exact material changes — 14 September 2026

Auction changes now appear in owner-private Today and Impact inbox panels, with
five-language reasons and links to a specific retained material event. Today has
a 48-hour material-change window; Inbox retains eligible unread changes. The
bounded reader selects one latest requested unread change per lot. A normal bid
increment does not reset its detection time, and an unrequested later change
cannot silently dismiss an earlier unread alert. Reviewing the current lot clears
the eligible signal; unfollow, pause, archive, profile/source replacement and
membership loss preserve their existing boundaries. An empty filtered page may
still have a continuation; changed or foreign cursors fail without revealing data.

The exact reader shows separately retained before/at-change snapshots and the
current lot/decision. It verifies record identity, the saved profile revision,
current ownership and each snapshot's permission/retention; expired or revoked
payloads are redacted. Historical material links remain stable when newer changes
arrive. Current review still requires the exact current state, permission and
version. Feed reads do not create decisions, collect sources, place bids or send
messages. No source URL or source description is copied into feed summaries.

Verification: 25 combined feed/API/private-workflow checks passed (39.60 s),
including exact CHF 8,500/12,700 snapshots, quiet bids, privacy, source revocation,
staleness, pagination, cursor invalidation, Today cutoff and profile replacement.
After hardening retention of an unread requested alert across an unrequested
later change, all 12 feed/API checks passed again (21.06 s).
The root isolated `auction-feed` build passed. The synthetic browser passed 13
checkpoints: Today → exact comparison → internal decision → empty Inbox,
five-language mobile viewer flows, source snapshot redaction and membership loss.
Desktop/mobile axe reported zero violations, no browser runtime exceptions were
recorded, and both screenshots were visually inspected. Unresolved manual axe
checks remain unverified; this is not live auction/source or human acceptance.

Native acquisition/current official reuse/category evidence, durable ending-soon
notifications and separately consented email remain open. The new panels display
changes from permitted retained records; they do not claim a configured live
Ticino collector. MV2-049/050 remain IN PROGRESS.
