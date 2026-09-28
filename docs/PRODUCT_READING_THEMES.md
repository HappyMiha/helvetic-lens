# Reading themes and shared device preferences

Status: DONE — scoped production reading themes, release 1.23. MV2-002/024
scope, dependencies, readiness and acceptance were recorded before code in the
sole Monitoring backlog. Both broader tasks and the full dynamic and visual
specifications remain IN PROGRESS.

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
The head script has no user-text interpolation. Native Next production and both
portable Sites production builds pass. Exact publication evidence follows below.

[Authored palette evidence](product-evaluations/2026-09-28-reading-themes-contrast.json)
contains 84 foreground/background, graph-label, input/focus and blended navigation
pairs. Minimum normal-text contrast is 5.062:1 and minimum tested control contrast
is 3.586:1. These numbers describe the authored pairs, not browser-computed,
disabled-state or whole-page accessibility certification. Remaining fixed colors
outside palette definitions are retained companion artwork and existing upstream
UI primitives; reading surfaces and graph/source-history colors now use tokens.

The final authored-control review also routes legacy form/button boundaries,
input utility colors and native controls through the tested input-border token.
Subtle evidence/container dividers keep their separate structural token. This
closes the distinction between a passing control palette and controls that still
referenced the weaker separator color. The affected 41 native shell cases,
production build, format gate and 5,466-file protected-value scan passed after
that correction. Both unchanged Sites 26 remained final.

## Exact production acceptance — 28 September 2026

Initial implementation 30be24fbfb5b1b1bca55e40d44348fe056b411a8 was committed,
immediately pushed and activated at 05:24:27 UTC. The final control-boundary
correction 8ea723c934b8afd338a110b1211777e09f53e99b was committed and immediately
pushed, then activated normally at 05:40:19 UTC. Public readiness returned exact
git-8ea723c934b8. Its healthy immutable web image matched all 40 selected compiled
navigation/theme assets and every native CSS asset to served bytes. The 43
native HTTP checks include exact pre-content theme scripts on login/monitoring
and the source-identical H favicon. Nine directions and five locale contracts
remain present in the compiled application.

Pharma 6f313aef2173484071ba3af918e76c5f829767b0 and Loyer
5b115962867cff306cbfa5e154e1e8a269f8d3d4 were immediately pushed to GitHub main
and the exact existing Sites source remotes. Both public Sites 26 completed
successfully, from the final portable archives. Each custom origin passed 125
HTTP/auth/guide/gateway/theme checks plus 47 exact served asset checks. Four
entry routes per product have the source-identical early theme script and one
global appearance control. The existing release verifier was updated to accept
the new capitalized accessible label instead of its stale historical wording.
GitHub CI runs 36381379602 and 36381381303 passed for these exact client commits.

The unchanged backend matched 57 source module hashes, migration 06d495bef125,
current-permission research schemas/queries, four native runtimes, five scheduler
modules and the minute schedule. Laya and the exact pinned local E5 retrieval
service were healthy. Model/parser probes used only synthetic local input.
No private production records, paid research requests or outgoing messages were
used for this acceptance. The API, schema, models and source approvals did not
change. All source and production assets passed the protected-provider-value
scans. The final backlog smoke passed before this acceptance was published.

[Sanitized exact-release receipt](product-releases/2026-09-28-1.23.0.json)
contains commits, archive identities, terminal Sites deployment records,
production checks and explicit limits. Authored contrast and programmatic checks
do not replace browser interaction, human visual/language or professional search
acceptance. Native global Ask/Search and remaining full-specification work stay
open; the existing hourly heartbeat continues.
