# Complete-scan health for IP and Auction monitoring

A clean final source page previously replaced the health of the entire scan.
If a retained original on an earlier page was corrupt or unavailable, the
monitor could finish as `current` after processing the remaining clean pages.
Both IP and Auction reproduced this behavior against real migrated databases.

Each private source cursor now retains `scan_unavailable_count` across page
transactions. Unavailable source evidence from any processed page keeps the
finished scan `partial`. The next scan starts a new count and can recover to
`current` only after its remaining pages are processed. Counts are scoped to the
existing private monitor and source cursor; changing the selected permission or
generation restarts the scan. Existing source locks, access checks, pagination,
matching, private decisions and delivery rules remain in force.

Migration `cfa2739cef02` adds nullable integer columns to the two cursor tables.
Existing rows retain their current keys and private histories. A null count
means that earlier-page health was never recorded. The normal worker restarts
that source scan at its first page instead of assuming the old prefix was clean.
This can cause one additional scan after upgrade. The migration does not rewrite
source evidence, events, reviews, monitor configurations or decisions.

The regression uses 51 source heads so both native page sizes cross a boundary.
It corrupts an original on the first page, opens a new database session for each
page, requires `partial` at the end, then restores that original and requires a
complete clean scan before `current`. Private item identities and versions must
survive. The legacy cases downgrade and upgrade the actual schema with a scan
in progress, verify metadata parity and prove that the unrecorded prefix is
rechecked. Source archives with unrelated private owners stay isolated through
the existing native access regressions.

## Verification

Before the repair, both new cases failed because the last page returned
`current` instead of `partial` (`.tmp/mv2-scan-health-reproduce.log`). The initial
repair and existing bounded-source regression passed four tests in 21.45s
(`.tmp/mv2-scan-health-fixed.log`). The expanded native business family run had
459 passing tests and two new migration-test failures in 406.84s
(`.tmp/mv2-scan-health-regression.log`). Those two compared unrelated tables whose
models were not imported by the focused suite. The corrected check compares the
complete schemas of both affected cursor tables, matching the repository's
existing scoped migration checks. Production code did not change after this run.

The final scan-health, bounded-source and backlog checks passed **7 tests in
33.83s** (`.tmp/mv2-scan-health-final.log`). These include ordinary and upgraded
unfinished scans, clean rescan recovery, metadata parity and exact preservation
of retained private decisions/reviews as well as item identities and versions.
The exact API Ruff gate and diff whitespace checks passed.

A separate PostgreSQL 16 migration roundtrip on the isolated nominal fixture
preserved 111 private IP candidates and 111 auction items, 222 history events
for each domain, and all 222 cursor bindings. Both complete cursor schemas match
their ORM metadata and all legacy counts remain unknown until normal processing.
The fixture had no recorded private decisions/reviews; the SQLite regressions
above establish preservation of nonempty decision/review rows. Evidence:
`.tmp/mv2-business-scan-pg-migration-roundtrip.log`. Local verification does not
establish production activation or the separate full capacity acceptance.
