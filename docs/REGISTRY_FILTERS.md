# Everyday registry filters

Monitoring and Discover share a compact filter surface. Search, detected-date
presets, impact, monitoring and read-state filters are immediately available.
Authority, connector, document kind, language, lifecycle, connector health and
exact dates sit inside a native disclosure. Existing advanced-filter deep links
open it and show their active values; unknown values remain in the URL with an
explicit unavailable label instead of silently changing the query.

The preset buttons resolve to the existing inclusive `start`/`end` date API
parameters. Today and Yesterday use calendar dates in Europe/Zurich, independently
of the browser's timezone. Last 7/30 days include today and the preceding 6/29
dates. Calendar arithmetic uses a UTC representation of that Zurich date, so DST
hours cannot shift the result. The resulting URL is a captured date range: opening
it tomorrow does not silently move it forward. These are detection dates, not
publication, decision or effective dates. Any time removes both endpoints.

Applied search, individual filters and date ranges have removable chips. Each
change resets pagination and preserves the other query values; clearing all
filters retains the canonical Monitoring/Discover route and locale. Browser Back
restores the previous URL-driven selections. A filtered empty result has a direct
clear-and-retry action. Unsaved search text remains local until submission.

Filter captions, fixed option values, time presets, coverage help and group
headings have DE/FR/IT/RM/EN messages. Language options use native language names.
This does not translate source titles, official date provenance, every legacy
server-authored label or persisted legal conclusions. Unknown metadata and richer
source-health recovery remain separate backlog work.

Search has a real accessible label, presets use pressed-state buttons, advanced
options use native disclosure, and primary controls/presets target 44 px. Long
row titles no longer compete with a non-wrapping date column on mobile. This
slice does not redesign all reading surfaces or claim independent accessibility
or usability approval.

## Verification

`npm run build` runs six calendar regression cases (spring/fall DST, Zurich
midnight, year/leap transitions and unrelated runtime timezones) alongside the
existing UI/resource/rendered checks. `npm run check:registry:browser` requires
20 populated isolated Chrome journeys: five locales × 390/1440 px × Monitoring
and Discover. It exercises real pointer hits, native search submission, option
changes, active-chip removal, URL Back recovery, empty-result reset, unknown
advanced values, cursor reset and viewer/admin control visibility. All API calls
are intercepted; no real registry mutation, source collection or AI is performed.
The existing four API registry tests also pass unchanged.

Remaining HL-095 work includes relevance/feed semantics, evidence-return scroll
position, topic route/history/crash draft recovery, comprehensive source health
and identity-mismatch recovery, physical mobile input and independent usability /
native-language review. The underlying registry read model still needs its own
large-corpus performance work; hiding advanced filters does not improve SQL cost.
