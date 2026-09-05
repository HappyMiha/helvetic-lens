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
plan. Navigating away/reloading can still lose an unsaved draft: a complete draft
navigation/recovery guard remains open HL-095 work.

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
preview retention/retry, expected revision and viewer read-only controls. No real
monitoring, AI call, source activation or production data is involved.

The contract is functional regression evidence, not native translation approval,
a complete screen-reader/keyboard audit, physical mobile keyboard certification,
proof of matching usefulness or a user study. Registry simplification, draft-loss
guards, full coverage health/recovery and independent usability gates remain open.
