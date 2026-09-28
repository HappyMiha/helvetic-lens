# Reading themes and shared device preferences

Status: IN PROGRESS — scoped visual continuation, release 1.23. MV2-002/024
scope, dependencies, readiness and acceptance were recorded before code in the
sole Monitoring backlog. Full dynamic and visual specifications remain open.

The native platform extends the Brandbook navigation frame with dark, light
and system reading palettes for its existing page surfaces, forms, tables,
source/evidence readers, comparisons, graph, dialogs and login. Semantic tokens
replace legacy hardcoded reading colors. Status meaning and evidence remain
unchanged; neutral surfaces no longer inherit a green/blue domain palette.
The existing companion character artwork and upstream UI primitives are retained.

Native login and the top bar expose the same accessible theme control as Pharma
and Loyer. All five native locales have labels. Dark is the initial preference;
an explicit light/system choice takes priority. A static first-party head script
applies the stored choice before content; the controller then maintains media
and same-origin storage listeners. This script receives no user, query or account
input and performs no network action. Invalid preferences fall back to dark.

The only stored value is dark/light/system under the existing
helvetic-lens-theme key. Storage failure keeps an in-memory choice for the current
page, including subsequent system changes. Unrelated keys/session-storage events
cannot reset it; a same-origin theme change or storage clear is reflected in
other tabs. Preference storage and bootstrap behavior are identical in all three
repositories. Cross-origin synchronization is not implied. Research context,
auth providers and child trees are not keyed or remounted by theme selection.

Both palettes retain meaningful status colors, readable selected text, visible
focus and input boundaries. The structural sidebar adapts to the reading theme
with an opaque fallback. Print selects a light reading palette; forced colors
use system colors and reduced motion retains state without decorative movement.
No new Lens animation, source classification or quality metric is introduced.

## Acceptance boundary

Required checks include valid/invalid/blocked-storage and first-paint parity,
system changes, cross-tab scope, listener disposal and actual localized server
markup. Existing native frontend/auth/draft/scroll/navigation contracts,
localization/types/build/format, both clients' tests/lint/types/portable builds,
the final backlog smoke and protected-value scan must pass. Authored palette
contrast, retained literal exceptions and exact deployed asset/HTTP evidence are
recorded separately. This background cycle does not establish browser-computed
contrast, human visual/language acceptance or professional research accuracy.

Native universal Ask/Search and the remaining full visual hierarchy/interaction
acceptance stay open. Completed investigation, contribution, public/private,
monitoring and semantic retrieval slices are preserved, not repeated. No API,
model, schema, source rights, provider setup, publication or delivery changes are
part of this release.


## Local evidence

The exact native frontend/localization/typecheck tree passes 367 cases; both
clients pass 129 tests, lint and strict types. Eight new behavioral cases per app
cover bootstrap/hydration preference parity, blocked storage, quota failure,
current in-memory choice, same-origin event filtering, disposal, unavailable
media queries and actual server-rendered controls in all five locale contracts.
The head script has no user-text interpolation. Native Next production and both portable Sites production builds pass. Exact
publication evidence is recorded after deployment.

[Authored palette evidence](product-evaluations/2026-09-28-reading-themes-contrast.json)
contains 84 foreground/background, graph-label, input/focus and blended navigation
pairs. Minimum normal-text contrast is 5.062:1 and minimum tested control contrast
is 3.586:1. These numbers describe the authored pairs, not browser-computed,
disabled-state or whole-page accessibility certification. Remaining fixed colors
outside palette definitions are retained companion artwork and existing upstream
UI primitives; reading surfaces and graph/source-history colors now use tokens.
