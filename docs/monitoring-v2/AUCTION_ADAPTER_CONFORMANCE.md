# Auction adapter conformance

## Scope and boundary

The AC-B8-12 fixture now exercises the complete source-to-private workflow for
two synthetic normalized adapter outputs, TI and ZH. Both use the same existing
production domain implementation. No runtime, source configuration, native
parser or live canton coverage is changed.

The fixtures use explicit synthetic permissions and reserved `.invalid` URLs.
Their raw bytes contain the normalized facts with an exact SHA-256 binding.
This is conformance at the **normalized adapter output boundary**, not evidence
that a Zurich publisher was inspected, licensed, parsed or connected. Native
Ticino HTTP/parser/collector evidence remains in [Auction Watch](AUCTION_WATCH.md).
Additional live cantons remain deferred under MV2-062.

## Executable journeys

[test_auction_adapter_conformance.py](../../services/api/tests/test_auction_adapter_conformance.py)
uses the real migrated database, source permission journal, scheduled projection,
authenticated private API and durable reminder planner. It covers:

1. TI and ZH independently: accept/replay a source receipt; create and start a
   private monitor; discover the exact source revision through the worker;
   follow and Inspect; activate the configured ending-soon reminder.
2. Change CHF 8,500 to CHF 12,700 against the CHF 12,000 limit, move the end time,
   and replace conditions/document hashes. Retain the earlier source facts,
   reopen review and replace the deadline reminder. No-bid remains internal.
3. A later bid increment retains review and the current reminder. Replaying the
   worker does not duplicate events, decisions or reminders. Explicit cancellation
   reopens review and invalidates all reminders; source history remains paginated
   and contains all four observations, including the non-notifying price update.
4. Unknown price, location and deadline stay unknown for both fixtures. No price
   match notification or deadline reminder is manufactured.
5. Wrong-canton and foreign-source evidence is rejected. A same-organization
   administrator has no access to another user's private items, history, exact
   events or reminders. Revocation redacts current facts and retained reminder
   dates, blocks source history and removes current feed/ready-reminder entries.
6. TI and ZH coexist with identical publisher auction/lot IDs. Their private
   identity, source history, revisions and review state remain independent when
   only one publisher changes its price.

The monitor's reminder schedule intentionally retains invalidated entries;
the shared ready-reminder list excludes them. A reviewed event can still be
read by its private exact link even after leaving the current actionable feed.
These distinctions are tested without deleting retained history.

## Validation and remaining acceptance

15 September 2026: the new module passed **7 tests in 33.21 seconds** on the local
SQLite test environment. Initial fixture checks used incorrect event names and
conflated the schedule with ready reminders; they were corrected to exercise the
existing explicit contracts. No production behavior was changed to satisfy them.
The required API Ruff gate passed. The only test warning was the existing
Starlette/httpx deprecation warning.

This closes the executable second-canton conformance gap identified by the
[acceptance protocol](ACCEPTANCE_PROTOCOL.md#ac-b8-12). It does not complete
MV2-050 or prove all AC-B8-01–12, PostgreSQL capacity, five-language visual
acceptance, SMTP delivery, independent relevance accuracy, current source rights
or exact production activation. Those have separate checks and evidence. All
broader release and human acceptance gates remain IN PROGRESS/NOT VERIFIED.
