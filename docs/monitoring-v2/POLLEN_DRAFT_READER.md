# Pollen Watch private draft reader

MV2-070 C01c1, 11 September 2026. `/pollen-watch` renders the existing private
draft API's list, current saved configuration and immutable configuration history.
It is a read-only interface, not the completed monitor creation or live workflow.
Creation/edit/delete and configuration preview forms remain C01c2.

The reader requires an authenticated user and workspace; anonymous development
does not receive a private identity. The server's exact default-off shadow grant
remains authoritative. A disabled workspace sees an unavailable explanation,
not a fake empty list. No serving configuration or navigation rollout is enabled
by this change. Access the route directly in an explicitly configured test
workspace. No Start request or other draft mutation is made by this page.

Each component instance is keyed by user, workspace and role. Switching identity
remounts it before private data can render under another scope. Unmount, reload
and selection changes abort outstanding requests; callbacks also check cancellation.
There is no local/session storage, shared resource cache or pre-rendered private
content. All API reads use the existing `no-store` helper and server authorization.
A failed read clears private list/detail/history and distinguishes disabled,
denied, missing and transient failure messages. Reload restarts pagination.

Lists read 20 records per page; histories read 10 revisions, using server cursors.
Selecting a draft reads its current settings and history together, retaining only
the newest selection's responses. Older history pages remain separate immutable
revisions. Saved Decimal values are displayed as strings without JavaScript
floating-point conversion. Rules retain their aggregation period and unit;
email, digest, quiet-hour and timezone settings are labelled saved preferences.
Neither those settings nor empty data establish active delivery or source coverage.

The page explains station-based measurement limitations, unavailable observations
and forecasts, and why Start is disabled. Native buttons/details provide keyboard
access; selection focuses the settings heading and brings it into view on mobile.
A specific contextual guide documents reading, pagination and the disabled action.
EN/DE/FR/IT/RM copy is provided for the interface. Independent native-language and
screen-reader acceptance remain pending; automated checks do not certify either.

`npm run check:pollen:browser` uses the actual production Next build and an isolated
headless Chrome profile. Every application API is intercepted with synthetic data;
the test never reaches a real workspace or pollen source. It checks five locales,
desktop/narrow layouts, keyboard selection, exact thresholds, pagination,
superseded requests and denied/default-off/missing/error/empty/anonymous/changed
workspace states. Full-document axe results retain incomplete checks for human
review. These checks establish component behavior, not live source or user readiness.
