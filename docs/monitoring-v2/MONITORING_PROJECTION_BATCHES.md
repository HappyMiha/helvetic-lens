# Bounded native record processing

Large public archives caused repeated source, configuration and private-item
queries even for records that had never matched a saved monitor. This repair
reduces that repeated work in Hazard, IP and Auction processing. It does not
change source admission limits, private projection page sizes or acceptance
thresholds.

## Behavior and retained checks

Hazard validates the saved monitor, source permission, source cursor and boundary
before loading its bounded current-head batch. Every retained message still
passes native identity, hash, retention, freshness and applicable publisher-poll
checks. A never-seen warning can skip event projection only when the native
decision function returns no decision. Existing developments and positive
decisions use the original projector, preserving outside-selection updates,
material versions, reviews and delivery behavior. Membership and geography are
rechecked after filtering; the worker retains its final source-proof, lease and
publication checks. An empty source accepts its valid zero cursor and still
checks private access. Unavailable evidence remains unavailable.

IP and Auction current-source pages join the selected heads with their exact
permission/record/revision identities. They stream ten rows at a time while the
existing permission and selection locks remain held. Native original/normalized
hashes, material fingerprints, retention, freshness and pagination are checked.
The source read takes four queries for either one or fifty records. Private
processing loads existing item keys once per page; only new, definitively
unselected records skip item projection. Unknown matches, existing history and
positive results keep their canonical processing. No cache crosses a request,
transaction, account or workspace.

## Verification

The initial Hazard source/lifecycle regression passed 84 tests in 42.04s.
The initial business source/workflow regression passed 79 tests in 55.05s.
These overlapping development checks preceded the final combined regression.
Tests cover fixed query cost, continuation without duplicates, retained original
corruption, permission revocation, private access, empty feeds, membership changes
during matching and a warning changing from outside to inside and back outside
the saved location. The combined affected Hazard, IP and Auction regression
passed **809 tests in 552.43s**, including APIs, source adapters, lifecycle,
matching and delivery (`.tmp/mv2-native-projection-regression.log`). Final
business negative-to-positive-to-negative history assertions and the backlog
integrity check passed **3 tests in 12.18s** (`.tmp/mv2-projection-final.log`).
The exact API Ruff gate passed. The standalone regression tests have no
dependency on the unfinished capacity-workload modules.

An isolated PostgreSQL 16 engineering probe used a synthetic archive with one
million native source observations, 1000 monitors and 100 accounts. Its selected
warning channel had 999 current heads, including one existing private warning
and 998 irrelevant warnings. Processing that same monitor changed from 12,001
queries / 77.297s to 36 queries / 1.140s, preserving zero new private events and
zero unavailable inputs. Logs: `.tmp/mv2-capacity-projection-pg-a.log` and
`.tmp/mv2-capacity-projection-batch-pg-a.log`.

The business probe advanced through three native pages per domain in that
archive. IP processed 30 records: the earlier pages took 268 queries / 1.766s;
subsequent pages after the repair took 90 queries / 0.766s. Auction processed 150
records: 826 queries / 5.093s before, 78 queries / 0.593s for subsequent pages.
The pages contain different keys because normal cursors advance; these timings
are illustrative observations, not an identical-record comparison or p95.
Both domains correctly remained `catching_up`.

These probes use an explicit frozen synthetic fixture clock, without HTTP,
official source access, SMTP or inference. They do not establish full private
catch-up, authenticated concurrent performance, fresh-change latency, target
hardware capacity, live source coverage or release activation. The separate
capacity-workload feature and parent MV2-054 acceptance remain in progress.
