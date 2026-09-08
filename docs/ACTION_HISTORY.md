# Human action decision history

## Complete pages — HL-099 / HL-092, 8 September 2026

The comparison UI requests `GET /api/comparisons/{id}?paged_actions=true`.
Its selected analysis contains one current decision and a count per action key,
an empty `history`, and `history_mode: "per_action"`. Opening a history loads
records on demand instead of shipping every historical decision with the report.

`GET /api/comparisons/{comparison_id}/analyses/{analysis_id}/actions/{action_key}/decisions`
returns `items`, `total`, `limit`, `as_of`, `first_cursor` and `next_cursor`.
The default page is 20 records; the server maximum is 50. Current decisions and
history use descending creation time and ID, including deterministic tied times.
There is no last-N cutoff: older records remain reachable.

The five product locales expose previous, next, retry and refresh controls.
A failed page request keeps the already displayed records; retry repeats that
same page request. Page changes focus the page-status text. Buttons have a 44px
minimum height and wrap on narrow screens. History uses 14px text at the default
root size and separated rows, replacing the inherited 9px presentation.
The current decision stays above the
history. A newly saved decision resets an open history; switching user,
organization, comparison, report, action or locale resets component state and
cancels pending requests. Reads have a 15-second client deadline.

## Scope and consistency

Every read rechecks the selected organization's analysis, the exact comparison,
and visible comparison/law parents. Decision rows additionally match the
organization, comparison and analysis explicitly, even in privileged sessions.
Historical reports remain readable; a history read does not rerun analysis,
enqueue work or record another decision. Existing write authorization still
applies to the POST endpoint. `paged_actions=true` on POST returns the compact
summary after saving; it does not change the decision itself.

The typed cursor binds organization, comparison, analysis, action and page size.
It captures a time ceiling plus a strict time/ID boundary; records created later
wait for refresh. Deleted boundary rows do not prevent continuing. This is not
a database snapshot: deletions, privileged corrections/backdated writes and
access changes can change subsequent results or totals. Refresh restarts history
with a new ceiling; it does not independently refresh the surrounding report or
another user's current decision.

## Compatibility and open limits

Without the opt-in flag the existing API still returns full `history` and
`current`. Its tied-time ordering now also uses ID. The web client still supports
that older response. Compatibility document/legacy readers remain unbounded.

Page reads select scalar decision fields and at most `limit + 1` rows; they do
not hydrate ActionDecision ORM histories. Compact summaries use SQL ranking and
counts and return one row per distinct action key. This bounds growth in repeated
decisions per key, not the number of distinct keys, the size of saved report/diff
bodies, or database ranking/count work. No new index or schema migration is part
of this change. Planner/index cost and intended-host capacity remain HL-099 work.

See [verification](VERIFICATION.md) for API, PostgreSQL and browser evidence.
Synthetic tests do not establish independent language quality, assistive-device
compatibility, usability or production performance.
