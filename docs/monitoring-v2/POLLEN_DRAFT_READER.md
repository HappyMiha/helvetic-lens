# Pollen Watch private draft reader

MV2-070 C01c1, 11 September 2026. `/pollen-watch` renders the existing private
draft API's list, current saved configuration and immutable configuration history.
The reader is now accompanied by C01c2a new-draft creation and configuration-only
preview. Existing-draft editing/deletion and delivery-preference editing remain
C01c2b; the live workflow is not implemented by this interface.

The reader requires an authenticated user and workspace; anonymous development
does not receive a private identity. The server's exact default-off shadow grant
remains authoritative. A disabled workspace sees an unavailable explanation,
not a fake empty list. No serving configuration or navigation rollout is enabled
by this change. Access the route directly in an explicitly configured test
workspace. The reader uses GET; the manager-only creator uses preview and create
POST requests through the existing CSRF-aware helper. No Start request is made.

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

## C01c2a new private drafts

An authenticated manager sees New Pollen Watch draft only after the workspace's
draft list loads successfully. The form accepts a station code, timezone, multiple
allergens and optional per-period threshold/reset and rapid-increase rules. Rapid
windows are offered only for hourly observations and forecast instants. Decimal
inputs stay strings; the server validates the complete v1 contract. Categories
cannot be enabled here, and email defaults to off. Station validation is not proof
that the selected live coverage exists.

Check settings performs a configuration-only preview without creating a record or
loading measurements. Any edit invalidates it. A separate Save stores the checked
server-normalized configuration. A synchronous in-flight guard blocks double
submission. After a potentially committed save, input and request key remain
frozen for an explicit retry. A lost response can therefore be retried within the
same open form without a second draft. Confirmed input-validation failures allow
correction; revoked access removes the form and private state.

The retry payload lives only in memory and is not recoverable after closing or
reloading the tab. Before-unload, clicked-link and workspace-navigation guards warn
about losing unfinished/uncertain work; Discard asks explicitly. Full browser
Back/Forward and crash recovery acceptance remains open for C01c2b. Retry uncertain
saves before leaving; after reloading, inspect saved drafts before creating again.
Successful saving offers explicit navigation to the saved record, with no Start.

The browser suite additionally checks creation in all five locales, keyboard form
entry, observation plus forecast rules, exact Decimal payloads, rejected preview,
preview invalidation, CSRF, duplicate clicks, a simulated committed save with a
lost response, same-key retry, saved navigation, discard decisions and revocation.
Five creator axe checkpoints bring the suite total to eleven. Native-language,
screen-reader, real workspace and source acceptance are still required.
