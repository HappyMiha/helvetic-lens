# Pollen Watch private draft reader

MV2-070 C01c1, 11 September 2026. `/pollen-watch` renders the existing private
draft API's list, current saved configuration and immutable configuration history.
The reader is now accompanied by C01c2a new-draft creation and configuration-only
preview, C01c2b1 confirmed draft deletion, C01c2b2 revision-checked numeric
editing, C01c2b3 delivery-preference editing and C01c2b4a saved-state recovery. The live workflow is not
implemented by this interface.

The reader requires an authenticated user and workspace; anonymous development
does not receive a private identity. The server's exact default-off shadow grant
remains authoritative. A disabled workspace sees an unavailable explanation,
not a fake empty list. No serving configuration or navigation rollout is enabled
by this change. Access the route directly in an explicitly configured test
workspace. The reader uses GET; the manager-only creator uses preview and create
POST requests through the existing CSRF-aware helper. Confirmed owned-draft
deletion uses the same helper with DELETE and the reviewed expected revision.
Existing-draft updates use PATCH with that same revision-checking contract.
No Start request is made.

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

## C01c2b1 confirmed deletion

Only a manager viewing an owned subject whose current status is draft is offered
Delete draft. The native confirmation names the selected station and exact
revision, and explains irreversible removal of configuration and evaluation
history. Cancel sends no request. A synchronous guard prevents duplicate
submission, and competing reader actions are disabled until the response arrives.

DELETE carries only the reviewed expected revision. On success, detail/history
are cleared and the list restarts with fresh pagination; a focused status message
confirms removal. A revision conflict retains the attempted view and blocks
another deletion until the user reloads the selected draft. The next confirmation
uses that newly read revision; no automatic conflict retry or unseen revision is
used. The server continues to enforce owner, organization, membership and lifecycle.

A failed response remains uncertain and offers explicit retry of the same
revision, or a list reload to inspect the result. A subsequent missing-record
response clears private data and reports unavailable rather than claiming that
this client proved deletion. Revoked/default-off access likewise clears private
state. Leaving the page aborts observation of the request, not necessarily a
server transaction that already committed; reread the draft list after returning.

Five-language browser checks cover exact confirmations, cancellation, successful
removal, double clicks, CSRF, fresh-revision conflict recovery, uncertain-then-missing,
revocation and active/viewer denial. Five post-deletion full-document axe checks
bring the combined suite to sixteen. Existing API/DB checks verify the private
cascades; no real user record is used by the browser fixtures.

## C01c2b2 revision-checked editing

An owner manager can edit a selected draft's supported numeric configuration.
The form clones the reviewed configuration, including contract/template metadata
and saved delivery preferences. Those preferences are displayed and preserved
unless explicitly changed through C01c2b3 below. Editing never activates delivery. Unknown fields, future
versions, units, allergens, periods and category rules keep the configuration
read-only instead of silently dropping settings the form cannot represent.

Every change invalidates the configuration-only preview. Saving requires another
server check and appends a revision using the originally reviewed expected revision.
There is no silent rebase onto an unseen revision. Conflicts freeze the attempted
settings until explicit discard/reload and review; cancellation retains the edits.
Duplicate clicks are synchronously guarded and access revocation clears private
state. Create and delete retain their existing contracts.

An uncertain PATCH locks the payload and original version. Check saved result
reads both the current draft and its exact next immutable revision, bounded by
`before_revision = expected_revision + 2` and `limit = 1`. A matching configuration
hash proves the requested settings are present in history, even if later revisions
exist. It does not attribute the write to this client or claim those settings are
still current; View saved draft reads the current record again. This recovery
does not issue another PATCH. Only a still-current original revision/hash in
draft status unlocks a separate explicit save attempt; conflicting state requires
reload/review. Original-revision CAS still protects against a delayed first write.

The five-language production-browser suite covers exact Decimal and metadata
preservation, saved delivery/digest/quiet hours, CSRF, duplicate submission,
conflict/discard/reload, lost-response and later-revision history recovery,
unchanged explicit retry, conflicting history, unsupported categories and revoked
access. Its 21 full-document axe checkpoints include the existing reader,
creation and deletion journeys. Compatibility tests reject future/unknown fields
without mutation. These are synthetic component/contract checks. Real workspace,
native-language, screen-reader, broader configuration editing, navigation/crash
recovery, source and live workflow acceptance remain open.

## C01c2b3 delivery preferences

Both new and existing supported drafts offer email off, immediate and daily digest
preferences. New drafts default to off. Selecting daily digest reveals a required
local time; changing the mode clears that time, and choosing digest again requires
a fresh entry. Quiet hours are optional and independent of email mode. Enabling
them requires explicit start/end times; disabling them clears the interval.
Overnight intervals are valid, equal endpoints are rejected with localized feedback.
Native time inputs require minute precision; the server remains authoritative for
clock, mode, quiet-hour and IANA timezone validation.

The form shows the selected timezone and explains that these are saved preferences
only. No live consent is granted, no scheduler is configured and no message is
sent. Runtime timezone/DST scheduling, consent and membership checks, opt-in and
unsubscribe remain C04/live acceptance work. Switching a draft to email off must
not be described as stopping an active delivery process that does not yet exist.

Every preference or timezone edit invalidates the configuration-only preview.
Saving uses the same idempotent create or expected-revision PATCH and uncertain
write recovery as numeric edits. Numeric selectors/rules and metadata are
preserved. The original delivery schedule remains available in immutable history;
the current revision displays the newly saved preferences. No browser persistence
or source call is added.

Browser checks cover all five locales, off defaults, missing clock fields, equal
and overnight quiet hours, midnight times, switching through all email modes,
explicit interval clearing, timezone labels, preview invalidation, exact create/edit
payloads, numeric preservation and lost-response history recovery. The API journey
also verifies rejected schedules cannot append revisions, old schedules remain in
history and no job or outbox message is created. These are component and contract
checks; actual email, human language/accessibility, source and user-test readiness
remain unverified.

## C01c2b4a saved-state recovery

Selecting a saved draft replaces the URL fragment with `#draft=<opaque-id>` while
preserving the current route/query and Next history state. The visible saved-draft
link can be reopened after a reload; it restores the current saved configuration
and first history page through the existing authorized API, not the revision that
was previously on screen. No configuration, request key, credential or permission
is carried by the URL. Browser local/session storage remains unused. A copied
identifier does not transfer owner/workspace access.

Failed, revoked, default-off and missing-record reads clear private state and the
locator. Starting a new draft, successful deletion and explicit list reset clear
the locator. Returning to an existing editor retains the selected saved identifier,
so a reload can read its server state; unsaved edits are not restored or represented
as saved. After an uncertain creation whose response did not reveal an identifier,
inspect the saved list before creating another draft. Memory-only retry keys and
unsaved fields cannot be recovered after a crash by this slice.

On `pagehide`, outstanding reads/mutations are aborted and private component state
is cleared synchronously before a document can be cached. A persisted `pageshow`
reloads the session as well as current settings, since another tab may have changed
the active principal. Ordinary Back/Forward document navigation is checked against
new saved revisions. Cancelling same-document history traversal while editing is
still open; this change does not use history sentinels or claim universal browser
navigation blocking.

Modified clicks, new-tab/download links and same-document anchors do not trigger a
discard prompt. An ordinary departing link asks once, then performs the confirmed
document navigation. Workspace/sign-out approval alone does not disable unload
protection; only the existing committed-navigation event does so after the action
succeeds. Browser-native reload protection remains in place for unsaved work.
The five-language form guidance explicitly describes the limits of recovery.

The implementation follows the installed Next native-history guide for preserving
router state. Navigation API traversal cancellation is not used as a substitute for
tested behavior; the [MDN overview](https://developer.mozilla.org/en-US/docs/Web/API/Navigation_API)
records limits on traversal cancellation. Full editing navigation/crash acceptance
requires a separate privacy-aware recovery design (C01c2b4b).
