# Auction Watch — B8

Status: IN PROGRESS, 14 September 2026. Scope: MV2-049/050 and auction-specific
contributions to MV2-043/044. Nine active directions remain; C4 stays deferred.
The previous integrated Monitoring implementation was pushed to main as
4859c58a8b255b40e30a6c2ae00d363e72f0d9dc. Auctions is the next complete direction.

## Required outcome

**Native acquisition feature scope, 14 September 2026:**
Finish official Aste UEF discovery/current-status/document acquisition through
the existing permission-scoped journal into private tracking, changes, reminders
and Today/Inbox. Include durable bounded resumable discovery, rediscovery and
known-item refresh, source lease/generation/rate/backoff checks, evidence retention,
parser-drift/partial-failure handling and a five-language read-only source-status
panel. Publish only once the whole collector→private workflow→visible status
journey and required tests/build/evidence pass. This is not a source licence or
completion of the broader B8 rights/category/human acceptance gates.

Current source inspection: two bounded anonymous HTML responses and the official
public JavaScript confirm listing links with `rel=next`, `/it/preview`, numbered
`/it/auction/{id}` pages and the read-only GET
`/it/api/auction/auction-status/{id}`. Status supplies an explicit end timestamp
and Europe/Zurich timezone, bid count and distinct highest-bid/current values.
The zero-bid detail labels its displayed amount as starting price; a current bid
must not be fabricated from it. Category filters belong to discovery evidence,
not guessed title words; missing location/brand/category stay unknown. Stable
document paths and hashes must distinguish list availability from byte changes.
Missing listings or inactive status alone cannot prove cancellation or removal.
The public robots file permits crawling, which does not establish reuse rights.
Firecrawl CLI is currently absent from PATH; primary HTML/JavaScript were inspected
via bounded public reads and the available web fallback. No production source
approval, account, bid, registration, contact or Firecrawl subscription was created.

Implemented parser boundary: `aste_parser.py` decodes bounded
HTML listings, acknowledged category filters, strictly advancing pagination,
detail identity, distinct typed prices, explicit status timestamps and stable
document references. Anonymous status amounts must agree with the formatted
highest bid before being admitted as a current bid. Unknown count/amount, missing
category/location/brand and unverified document bytes stay unknown. Ambiguous DST
start dates are not guessed. Inactive status cannot establish cancellation.
`aste_transport.py` admits only fixed-origin public GET listing/detail/status/PDF
paths; it rejects action endpoints, inherited auth/cookies/queries, redirects,
unbounded or encoded responses and false PDF bodies. It calls the supplied lease/
rights guard before and after every transfer and preserves publisher Retry-After.
The final parser/transport suite passed 50 checks (0.37s); exact API Ruff passed.

Offline replay of captured official responses decoded 50 current-list entries
with a page-2 continuation, 69 upcoming entries and 32 explicitly filtered bicycle
entries. These are individual observed pages, not a verified complete catalogue.
The upcoming list contains additional art categories; no real-estate/vehicles/
equipment coverage is established. The captured auction 185 response produced a
CHF 20 starting price, zero current bids, an explicit Zurich end time and two PDF
references. Document contents were not downloaded. Source captures remain ignored
local research files; committed tests use synthetic content and claims.

The whole acquisition feature is now implemented and tested; see the
[native collection evidence](#native-collection-and-visible-source-status--14-september-2026).
No production source approval or full-category coverage is implied.

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

## Durable reminders and consented email — 14 September 2026

Following a lot with a configured ending-soon interval now retains a private
reminder for its profile/deadline generation. Due work runs every 15 seconds and
rechecks the current source, ownership, follow state and known future end time.
Moving a deadline away and back creates a new generation; quiet bid increments
do not create another reminder. Pause, unfollow, cancellation, postponement and
unknown/expired deadlines invalidate obsolete work. Transient source staleness
defers the check with bounded backoff. Acknowledgement survives replay and
refollow without marking the lot reviewed or placing a bid.

Each profile exposes its bounded reminder schedule. Due reminders also appear
in Today and Impact inbox, with a private exact link to the reminder and current
lot. Access and source evidence are rechecked on each read; revoked/superseded
source deadlines and payloads are redacted. Filtered pages can continue even
when empty; changed/foreign cursors do not disclose another user's work.

Separate verified-account email consent supports immediate or daily delivery,
IANA time zones and quiet hours. Saving profile notification choices does not
grant email consent. Delivery considers new requested unread material changes
after consent and current ready reminders, with a 48-hour intent horizon and
at most one daily attempt per profile/local day, including consent changes.
The private queue records references and hashes, not another licensed payload.
Emails contain authenticated links and detection times, not auction source
facts. Prepared work rechecks source display/matching/notification permissions,
current evidence, membership, recipient binding, consent, review/follow state
and reminder eligibility at claim and immediately before SMTP. Off/pause/archive
cancels pending work; acknowledgement, changed deadlines and revocation also
suppress stale prepared reminders at the final boundary.

The existing durable maintenance worker sends at most 50 items per attempt.
Deferred candidates move back so a stale lot does not continually block fresh
work. SMTP exceptions and abandoned send claims are recorded as uncertain and
never automatically resent. Signal identity survives consent changes; a sent
or uncertain reminder is not resent for the same lot/deadline/interval merely
because email was toggled. This is per-private-profile deduplication, not a claim
of global deduplication across independently configured monitors.

Migrations `92df5013b194` and `a3e06124c2a5` add organization-scoped reminders,
append-only email policies, durable intents and the monitor consent revision.
Both use explicit schema operations. Rollback/upgrade and metadata comparison
preserve existing profile/source state. All routes retain authenticated private
ownership, normal CSRF, strict input/CAS checks and no-store responses.

The root isolated `auction-reminders` build and exact API Ruff gate passed.
Initial integrated API/workflow/reminder/delivery checks passed (49), followed
by a real HTTP-to-durable-worker dispatch check with a fake SMTP mailer (1).
The synthetic browser passed 14 checkpoints covering Today/exact reminder,
explicit email consent/preview, acknowledgement without lot review, five-language
mobile readers, source revocation and membership loss. Desktop/mobile axe
reported zero violations; both screenshots were visually inspected and no
browser runtime exceptions were recorded. Incomplete manual axe items remain
unverified. The final expanded source/rules/feed/API/workflow/reminder/delivery
and backlog suite passed all 122 checks (86.80 s), including filtered reminder
pagination, cursor invalidation and fair delivery behind a stale lot.

This completes the private reminders/email outcome for permitted journal data.
No live auction mail, source account, grant, collector, external bid or owner
inquiry was created. Native official acquisition/current reuse/category evidence,
native adapter conformance, verified activation and human acceptance remain open.
All nine section switches remain enabled in production; missing source access
is shown inside the section. MV2-049/050 remain IN PROGRESS.

## Native collection and visible source status — 14 September 2026

The Aste UEF worker now connects current/upcoming listings and acknowledged
category-filter pages to complete detail/status/document observations in the
existing journal, private tracking, material-change history and reminders.
Missing auctions are revisited by their known public identity. Neither absence
from a listing nor inactive source status invents cancellation.

Migration `f8d5b67917fa` adds durable acquisition state, per-item stages and
listing evidence without changing private decisions. One committed source lease
guards each anonymous fixed-origin GET before and after transfer and again at
journal admission. Crashed claims expire; late workers and replaced permissions
cannot admit old responses. Publisher backoff survives restart and permission
replacement. Discovery alternates with item refresh, prioritizing in-flight
observations so bounded HTML/status/PDF acquisition can finish before expiry.
Limits are 5,000 known identities, 1,000 pages per scan, 10,000 retained listing
proofs and 128 MiB of acquisition payloads. Capacity failures preserve the retry
checkpoint and do not publish a partially accepted page.

An approved native access plan explicitly names request spacing, permission to
download documents and exact official category ID/label mappings within the
source's reviewed category scope. Fresh, intact category listing evidence is
required; mismatches, stale proofs and conflicting mapped categories remain
unknown. Each PDF is bounded to 16 MiB, checked as a PDF and hashed; only the
hash, byte count and receipt timestamp are retained, not a downloadable PDF copy.
The final status is fetched again after documents. The journal bundle retains
exact HTML/status bytes, category provenance and document receipts under source
retention. Raw/normalized listing expiry and revoked transient payloads are
cleaned even when the section is disabled. Historical licensed journal data and
private decisions remain governed by their existing independent retention gates.

`ASTE_SOURCE_ENABLED` defaults to true in production and application settings.
`ASTE_SOURCE_PERMISSION_ID` must name a reviewed, selected source permission
with `native_access.adapter_version = "aste-public-v1"`; no grant, default
category mapping or credentials are seeded. The five-second scheduler is only a
wakeup: durable request spacing, source refresh periods and backoff govern GETs.
The authenticated no-store source-status reader never starts collection. The
five-language Auction Watch panel exposes missing access, collection counts,
retry attention, the latest complete observation, listing completion and partial
coverage. All nine active sections remain visible on desktop and mobile.

Validation: 189 affected checks passed across the combined and final focused
runs. The final 44-check acquisition/source run passed in 28.91 s, including
native HTTP→private review, PDF/end/price changes, reminder replacement,
owner-private Today, revocation redaction, restart/lease replay, permission
replacement, malformed/capacity rollback, category freshness/integrity and
migration downgrade/upgrade preserving decisions. The other 145 affected
parser/transport/profile/rules/API/workflow/feed/reminder/delivery/backlog
checks passed in the combined run. No live SMTP or official PDF request is
part of these tests.

The isolated root `aste-source` build, exact API Ruff and changed frontend
formatting passed. The built browser journey passed 29 checkpoints, including
all five mobile languages, read-only refresh, failure clearing, private tracking
and membership/source revocation. Four axe audits reported zero violations;
the source-status desktop/mobile screenshots were visually inspected. Manual
accessibility and human pilot acceptance are not claimed.

Source reuse/access approval, real category/canton coverage, operational request
budget sizing and verified activation remain open. The main site's ready
endpoint still reports `git-99da831d934a`, instance main, database/Redis healthy.
No deployment was restarted or duplicated. MV2-049/050 remain IN PROGRESS.
