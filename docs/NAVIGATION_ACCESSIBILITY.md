# Navigation focus contract

The first keyboard stop in the application shell is a localized **Skip to main
content** link. Activating it focuses the actual content container without forcing
users to traverse desktop or mobile navigation first.

At widths up to 900 px, **More** opens the existing shared Radix dialog. The menu
has a localized accessible name, traps forward/reverse keyboard focus, hides
background content from the accessibility tree and locks background scrolling.
Close, Escape and an outside click restore the More button. If the workspace
selector is expanded inside the menu, the first Escape closes only that selector.
Resizing to desktop closes the mobile dialog and focuses the main content, rather
than an invisible mobile button. Successful route navigation closes the menu;
existing profile draft guards and organization authorization remain authoritative.
Marvin is temporarily hidden while the mobile navigation is open, without clearing
his conversation or preferences.

The same role-filtered route fragments are used on desktop and mobile. This UI
filtering is not a replacement for server-side authorization.

## Reproducible checks

Run `npm run build` and `npm run check:shell:browser`. The latter starts disposable
Next/Chrome processes on an unused loopback port and intercepts every application
API request with synthetic responses. It requires a populated inbox and checks
DE/FR/IT/RM/EN, viewer/organization administrator/platform administrator roles,
390/768 px and transitions to 1440 px. It exercises real key/pointer events,
focus, scroll restoration, nested Escape and visible role-filtered links. No
organization is changed, provider called, message sent or production data used.
Screenshots and failures stay in ignored `test-results/shell-navigation/`.

This is a focused Chromium regression, not complete WCAG certification. Nested
Marvin/evidence dialogs, other required seeded routes, automated whole-route
accessibility scans, native-language review, screen readers, Firefox/Safari and
physical mobile software-keyboard/audio checks remain separate HL-097 gates.


## Marvin to cited Ask — 6 September 2026

On a comparison, Marvin's explicit **Open cited Ask** action transfers the trimmed
question to the comparison question field, closes Marvin and focuses that field.
It does not submit the AI question, reload the document or depend on a running
local model. At overlay widths the comparison retains its own scroll lock while
Marvin releases his; dismissing Ask returns focus to the persistent opener and
restores scrolling. The transferred draft survives closing/reopening Ask.

Personal handoff history saves in the background, with a ten-second request
deadline and no automatic retry. An unavailable or slow history service does not
prevent editing/submitting the transferred draft. Failed/timed-out saves are not
presented as saved history; the draft remains in Ask, but this is not a durable
offline history queue. A response from an earlier handoff or detached/changed
context cannot replace the current personal history. No provider request is sent
until the user explicitly submits Ask.

The mandatory comparison browser suite adds five locales × four widths × available
or held personal-history responses (40 real handoffs), including 2,000-character
multilingual drafts, focused Ask before the held response is released, late error
handling, and an old successful response after detach/reattach of page context.
It also checks exact request payload, one personal save, no implicit AI submission,
no full reload, close/reopen draft and focus/scroll behavior. All APIs are synthetic
and intercepted; no real data or model is used. These journeys complement the
existing populated comparison/evidence and Marvin-monitoring suites, without
claiming every modal combination, screen-reader or physical-device acceptance.

## Marvin panel focus — 6 September 2026

Marvin's open panel is a named native dialog. At widths up to 1350 px it opens
modally: background content cannot receive keyboard focus, root/main scrolling
is locked, and forward/reverse Tab stays within visible enabled controls. Below
900 px the existing full-screen layout remains; tablet widths retain the side
drawer and backdrop. The close target is at least 44×44 px. At wider widths the
panel is nonmodal and the existing reserved main-column space remains usable.
Escape outside this desktop panel does not dismiss it.

Opening focuses the close control. Close or panel Escape restores the actual
opener, without scrolling it unnecessarily; a disconnected/hidden opener falls
back to the persistent Marvin button. The drawer owns its Escape instead of a document-wide companion listener.
A nested dialog owns its own Tab/Escape, so dismissing that child does not dismiss
Marvin as well. Pointer dismissal requires a press and release on the backdrop,
not a drag beginning inside the drawer. Viewport changes keep the same subtree,
focused control and unsent draft. Closing/reopening retains the companion's draft.

Marvin and the comparison overlay now share scroll-lock ownership. Original root
and main overflow styles return only after the last native overlay releases them,
including out-of-order cleanup or a route replacing the main element. The helper
does not inspect form values/text for assistant context; it manages element styles
only. Existing Radix navigation and its independent body scroll handling remain.

`npm run check:marvin:monitor:browser` requires two saved user messages and an
assistant reply on the actual Topics page with the local model stopped. It checks
five locales × 390/768/1024/1440 px × reader/admin, real Tab/Shift+Tab/Escape,
programmatic background-focus rejection, close reachability, draft-preserving
resize/close, transient-opener fallback, tablet backdrop-versus-drag dismissal,
released locks and the existing explicit monitoring handoff without
sending messages or activating a topic. A synthetic native child dialog checks
nested Escape ownership; it is not proof of every real cross-feature modal flow.
The old unrelated `.marvin-panel` dismissal selector was corrected to the actual
open `.marvin-drawer`, so navigation cannot pass while the real panel stays open.

Four scroll-ownership regressions run in `check:shell`; build, existing navigation,
comparison/evidence and scoped contrast suites provide additional evidence in
`VERIFICATION.md`. Phone and desktop screenshots were inspected. Full assistive
technology, physical keyboard/software-keyboard/audio, Firefox/Safari, whole-route
accessibility scanning and all real Marvin-to-evidence/handoff combinations remain
open HL-097 gates. These checks are not a WCAG certification or native-language
usability approval.
