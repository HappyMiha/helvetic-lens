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
