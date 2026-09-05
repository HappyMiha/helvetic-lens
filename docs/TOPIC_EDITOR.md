# Progressive monitoring-topic setup

The topic editor begins with a plain-language goal, a short name and matching
terms. The terms and synonyms drive the existing deterministic matcher; the goal
explains the organization's intent. Manual setup and preview need no AI provider.

**Sources and scope** and **Refine matching terms** disclose the existing expert
fields. Source-pack names come from the localized catalogue; document/event types
have DE/FR/IT/RM/EN labels and language choices use their native names. Saved-topic
cards also display catalogue names instead of source-pack IDs. Unknown catalogue
entries are explicitly unavailable, not silently replaced with another source.

New plans initially select only already enabled source packs. Polling never
reselects a deliberately cleared option. Selecting another pack in a topic is a
matching rule, not authorization to connect or activate that pack. A separate
Sources link explains how to manage coverage. The summary counts selected packs
and languages; it does not invent future event volume or completeness.

A missing scope opens the relevant disclosure and explains the required choices
before sending a request. Preview is read-only; saving/activation remains a
separate explicit action with existing idempotency and revision checks. Pending
preview/draft/save work disables the editable plan and topic-switch actions, so a
late response cannot overwrite newly typed fields. Failed previews preserve the
plan. A visible unsaved-change indicator compares the edited plan with the loaded
or reset baseline. Starting a new topic, cancelling an edit or editing another
saved topic asks before discarding changed fields; cancellation retains the plan
and returns focus to it. Unchanged/reverted plans and successful saves do not ask.
Reload/document unload uses the browser's native warning after user interaction.
Meaningful unsaved changes also persist in **sessionStorage for this tab**, scoped
to the current user and organization. Returning through a client-side route or
reloading offers Restore / Discard above the editor; nothing is restored, submitted
or activated without that choice. The editor remounts on identity changes, so one
account or organization cannot inherit another's in-memory plan.

The saved draft contains editable fields, the original baseline and topic revision,
minimal AI-draft attribution (if present), and the activation idempotency key.
Restoring does **not** restore old preview results. A fresh preview is required
before saving. A failed activation followed by reload retains its key, allowing the
server to deduplicate a retry whose previous outcome was uncertain. Concurrent
server edits still fail the existing expected-revision check rather than being
overwritten; restoration never silently upgrades to a newer server revision.

Reverting to the baseline, accepting a discard or successfully saving removes the
stored draft. A draft expires after 24 hours without an edit; expiration is checked
on read. Invalid, oversized (over 65,536 serialized characters) or incompatible
records are discarded. Storage denial/quota failure displays an explicit warning;
manual editing still works. Unknown metadata/preview data is not serialized. No
API calls or model inference are used for browser draft persistence.

This is a convenience copy, **not a backup or cross-device sync**. Storage is local
and unencrypted, not a security boundary against someone using the same browser
profile or same-origin scripts. Signing in to another account does not reveal the
original draft, but returning to the original account in that tab can recover it.
Closing the tab, browser eviction, private-mode restrictions, crash/OS termination
or clearing site data can remove it; preservation of the final keystroke during an
abrupt kill is not guaranteed. Only explicit server saving is durable. Complete
client-route discard warnings and physical mobile/crash recovery remain open.

Editing a topic at the bottom of a long list scrolls the actual editor into view,
accounts for the sticky toolbar height and focuses its loaded name field. This
works with the shell's main scroller as well as a document scroller.

## Verification

Build with `npm run build`, then run `npm run check:topics:browser`. The isolated
production UI uses 30 synthetic saved topics and two synthetic source packs. All
application API requests are intercepted. The required ten populated journeys
cover five locales at 390/1440 px, pointer reachability, real catalogue polling,
manual preview/explicit activation, idempotency, hidden-scope recovery, busy-state
protection, long-list editing and horizontal layout. Additional cases check failed
preview retention/retry, expected revision and viewer read-only controls. Forty
localized discard decisions check acceptance/cancellation across the ten journeys;
a real native beforeunload dialog is cancelled to retain a failed-preview draft.
Successful saving removes that guard before leaving. Ten additional accepted
reloads (five locales × two widths) require explicit restoration, preserve the
baseline and never submit automatically. Additional browser checks cover failed
activation/reload/same-key retry, actual client navigation/Back, storage denial,
user/organization isolation and explicit saved-draft discard. Thirteen parser/storage
unit cases cover expiration, malformed shapes, bounds, scoped identity, attribution
and removal. No real monitoring, AI call, source activation or production data is
involved.

The contract is functional regression evidence, not native translation approval,
a complete screen-reader/keyboard audit, physical mobile keyboard certification,
proof of matching usefulness or a user study. Complete route/history discard
warnings, full coverage health/recovery, cross-device durability and independent
usability gates remain open.
