# Complete saved document history

Implemented on HappyDucky02, 6 September 2026, for HL-099.

The document page now shows 20 records at a time for saved versions, saved
comparisons and fetch/import observations. Previous, Next, Retry and Show latest
controls reach the complete accessible history. Observations stay behind their
existing disclosure. Paging updates only the relevant list; it does not navigate
away, scan a source, generate an answer or modify a saved record.

The displayed total is a database count of accessible records saved by the page's
cutoff, not a source-coverage claim. The label that previously described every
comparison list as the latest 50 pairs is replaced by its count. A sparse or empty
page is distinct from proof that a legal source has not changed.
The cutoff is displayed with date, seconds and the Europe/Zurich time zone.

## Selecting older versions

The comparison and scan selectors contain the recent 20 versions, the currently
displayed history page, the current live version and at most three explicitly
selected records. Selecting an older baseline also selects it as the comparison's
earlier version, as before. Selecting either comparison side keeps that choice
while browsing other pages. A current live version outside the first page remains
selectable. Importing a new historical version retains it immediately in the form;
deleting a selected import clears its choices.

Selection and cursor state reset on document, user or organization changes. They
are in-memory interaction state, not a new durable monitoring preference. Reloading
starts from the latest records. Exact evidence and comparison links remain the
existing durable URLs. Version selection still requires an explicit scan/compare
button before any operation; viewers can browse without gaining mutation rights.

## API and read cost

- `GET /api/laws/{id}?paged_history=true` returns the existing arrays with their
  first 20 items and a `history_pages` entry for each list. Each entry contains
  `total`, `as_of`, `limit`, `first_cursor` and `next_cursor`.
- `GET /api/laws/{id}/history/{kind}?limit=20&cursor=…` returns that metadata plus
  `items`; kind is `versions`, `comparisons` or `observations`. Limits are 1–50.
- The original unqualified document detail remains compatible: all version
  summaries and the existing 50-comparison/100-observation previews. The web app
  opts into the new contract, rather than silently changing external consumers.

Each nonempty page executes four history queries: current watch/law access, a
scalar count, at most `limit + 1` saved-time/ID keys, and metadata for the selected
IDs only. HTTP service configuration reads are separate. No historical Version,
Comparison or Observation objects are hydrated. Text/passages/diff bodies and
artifact storage keys are not returned. Character/passage/page counts and diff
counts retain the existing SQL projections; other metadata fields are unchanged.

The total count and sorting still have database cost proportional to indexed
history, and individual metadata fields are not byte-capped. The law summary's
current-version/selected-comparison reads and the separate regulatory timeline are
not made fully bounded by this change. Target-host workload testing remains open.

## Cursor and access contract

The typed base64 cursor binds organization, law, history kind, page limit, save-time
cutoff and last `(created_at, id)`, or an explicitly unpositioned first page. The
first cursor does not rely on a sentinel ID's collation. It has a size limit and rejects mismatched,
malformed, extra-field and future-cutoff inputs. It is not a signed access token;
every request explicitly rechecks the current organization's watch and law/record
ownership, including privileged database sessions. Paused watches retain readable
history. Foreign observations and private version/comparison rows are excluded.

Next uses strict descending keysets. Deleting the boundary row does not invalidate
continuation or shift it like an offset. Back uses the original first cursor,
not a fresh list with a different cutoff. New saves after the cutoff wait for
Show latest. This is **not a transaction snapshot across requests**: corrections,
deletions, visibility changes and deliberately backdated inserts may change old
pages and counts. No cursor grants access to removed membership. A discovered
session-resolution bug is also fixed: a removed membership yields an anonymous
session/401 on protected reads instead of an unhandled server error, while public
sign-in and session routes remain usable.

Migration `d5b7cf062983` adds `(law_id, created_at, id)` indexes on versions and
comparisons and `(organization_id, law_id, created_at, id)` on observations. It
does not rewrite saved evidence. Downgrade removes only these indexes. A production
operator must plan index creation for the actual archive; committing this migration
does not authorize deployment or claim nonblocking production index creation.

## Verification boundary

API tests traverse 152 versions, 151 comparisons and 502 observations, including
same-time ordering, old-page access, scope, boundary deletion, late saves and
populated upgrade/downgrade. The standalone PostgreSQL runner requires an empty
case-specific localhost scratch database and refuses existing tables or remote
hosts. Browser coverage uses the production build with intercepted synthetic APIs
in DE/FR/IT/RM/EN, administrator/viewer roles, keyboard and 390/1440px layouts.
See [the dated verification record](VERIFICATION.md) for completed runs and limits.
Independent native-language, screen-reader, physical-device and target-hardware
acceptance are not established by these tests.
