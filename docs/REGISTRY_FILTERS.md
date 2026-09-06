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

Remaining HL-095 work includes relevance/feed semantics, complete topic route/history/crash
draft recovery, comprehensive source health
and identity-mismatch recovery, physical mobile input and independent usability /
native-language review. The underlying registry read model still needs its own
large-corpus performance work; hiding advanced filters does not improve SQL cost.


## Return to a registry record (6 September 2026)

Opening saved evidence, a timeline or a comparison from a registry row records one
short-lived reading marker in this browser tab. It contains the exact registry or
Discover URL (including filters/search/cursor/locale), row ID and destination, scoped
to the current user and organization. It contains no document text or AI answer.
Only ordinary same-tab Next navigation records it; opening an external source or
using a modified/new-tab link does not overwrite the current reading position.

On return to exactly that result URL, the loaded row's original link receives focus
and scrolls into view below/above viewport navigation. Centering the link itself
also works for a card taller than the viewport. If that link changed, the matching
row receives focus. A marker is consumed once to avoid repeated jumps on refresh.
If the successfully returned page no longer includes the row, a localized notice
explains its absence without changing filters or selecting another record. A load
error does not consume the marker, so retry/reload can still restore the position.

Both saved-evidence viewers additionally offer **Back to your results** when their
exact destination matches the same scoped marker. Otherwise their existing back
link remains unchanged. Timeline and comparison pages keep their existing navigation;
native browser Back from those registry departures can restore the original row.
No arbitrary return URL is accepted: only the two registry routes and local evidence,
timeline or comparison destinations pass validation. This is navigation convenience,
not an authorization boundary; existing API permissions still control returned data.

The marker expires after 30 minutes, is overwritten by the next departure, and never
becomes server-side or cross-device history. Storage denial leaves ordinary links
and browser Back usable without automatic row restoration. A restored browser tab
or a browser-managed duplicated tab may retain session storage; this is not durable
backup or a promise of isolated browser duplication. Existing resource caching still
applies; a reading marker does not freeze a result snapshot or certify freshness.

Monitoring/Discover controls now use a labelled navigation landmark, real links and
`aria-current="page"`. They no longer claim tab/tab-panel keyboard semantics for
separate routed pages. The normal forward Tab order is tested in the actual browser.

Verification adds seven storage/validation cases and 20 populated round-trip journeys
(five locales × mobile/desktop × both registry routes), each opening record 20 and
returning with both the evidence link and native Back. The final record has a title
long enough to exceed a screen; focus must remain visible without a document reload.
The suite preserves filters/cursor, consumes the marker and checks a removed record
on a newly fetched page. The original 20 registry/filter journeys and ten paginated
saved-evidence journeys remain required. These are isolated Chromium fixtures, not
physical-device, screen-reader, native-language or independent user acceptance.
