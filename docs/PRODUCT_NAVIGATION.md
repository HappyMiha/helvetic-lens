# Shared product navigation and native identity

Status: IN PROGRESS — scoped visual continuation / release 1.22. Scope,
dependencies, readiness and acceptance were recorded before implementation in
BACKLOG_MONITORING_V2.md under MV2-002/024. Both parent tasks and the full dynamic
and visual specifications remain IN PROGRESS.

## User outcome

Pharma and Loyer now expose the same product destinations in their workspace
sidebar, global Ask / Search and guide. Anonymous readers of public dossiers can
reach the same links through the global command surface without registering.
The native Monitoring platform exposes them in its desktop navigation and mobile
drawer. The current product is identified as a non-navigating current location.
Other products open in a new tab, preserving the current dossier and unsaved work.

The only destinations are https://pharma.helveticlens.ch/,
https://loyer.helveticlens.ch/ and https://helveticlens.ch/. Plain anchor links carry
no query, dossier ID, return URL, identity, token or private context. They use
noopener, noreferrer and an explicit no-referrer policy. No opener window is
retained. There is no automatic navigation, prefetch, sign-in, provider request,
permission grant or publication. Destination authentication remains authoritative.
These links do not merge product data, change organizations or share a dossier.

## Brandbook continuation

The native wordmark/favicons use the geometric H instead of the older magnifier.
The existing sidebar gains Carbon/Obsidian/Frost, a structural 30px glass layer
with an opaque fallback, readable current navigation, keyboard focus and quiet
boundaries. The surrounding native reading canvas is neutral light with a 1440px
regular content limit; existing wide comparison layouts retain their space.
All nine Monitoring destinations remain in the same desktop/mobile navigation,
including directions whose source access is not ready. Administrative controls,
workspace switching, unsaved-form guards and sign-out are unchanged.

Both product clients keep their current light/dark/system preference and Lens
behavior. New destination blocks use existing semantic tokens and 44px targets,
with no animation. Native navigation supports forced colors and reduced motion.
Source reading, legacy native page bodies and their remaining complete dark/light
migration are separate work. This release does not assert a complete native
visual migration or human visual acceptance.

## Validation and production boundary

The fixed-origin/current-location component and copy are shared across all three
applications. Actual React rendering checks verify both external destinations,
new-tab/opener/referrer semantics and absence of injected private context for
all current-product choices. Native English/German/French/Italian/Romansh strings
cover current location, destination meaning and the new-tab behavior; independent
language review remains open.

Local checks pass: 359 native frontend cases across the existing shell, resource,
report, help and graph gates plus the new rendering contracts; localization and
strict native types; 121 tests, lint and strict types in each product. Native and
both portable production builds complete. The exact API code and database schema
are unchanged. The Monitoring backlog smoke gate passes. Source/asset integrity,
secret scanning and exact production acceptance are recorded after publication.

Eleven authored navigation palette pairs meet the 4.5:1 normal-text threshold;
minimum 5.06:1. The glass calculation uses 94% Obsidian over the light canvas.
[Contrast receipt](product-evaluations/2026-09-28-navigation-contrast.json).
This is a token calculation, not browser-computed whole-page certification.
No browser preview, screenshot, interaction QA, human visual/language sign-off,
private production records, outgoing messages or paid provider calls are used.

The twenty-step dynamic dossier Definition of Done was reviewed against the
completed scoped investigation, contribution, team/guest, living-public,
evolution, monitoring and retrieval releases. This navigation work changes none
of their authority or research contracts and does not replace the remaining
combined acceptance or independent professional-quality work.
