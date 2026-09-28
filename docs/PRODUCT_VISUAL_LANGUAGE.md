# Product visual language — reference dossier

The owner's [complete brief](VISUAL_LANGUAGE_SPEC.md) governs the visual direction.
Release 1.9 applies its shared foundation and first reference dossier to both
Pharma and Loyer without replacing the existing application stack. The full
native-platform page migration remains incremental; this is not a claim that all
legacy platform screens or the dynamic dossier specification are complete.

## Architecture and experience

The root ResearchEnvironment owns the device-local light/dark/system theme and
UniversalAskSearch. AppShell, GlassSidebar and TopNavigation reuse native client
navigation primitives. Sidebar material alone is persistently translucent. Other
surfaces are neutral, opaque and readable. Shared tokens define typography,
spacing, surfaces, status colors, motion and the limited optical treatment.
Existing source libraries, setup, discussions, files, exports and public readers
retain their original permission and storage contracts.

Cmd/Ctrl+K opens the same global interaction on every product route. Typing alone
makes no search request. Anonymous public-dossier search, current authorized
workspace all-word search, deliberate public-web discovery and the current
private dossier investigation use their existing native APIs. Public search has
visible disclosure; private saved material is not turned into an external query.
The entry point requires no model, provider or pipeline selection. Existing
multilingual, saved-search and comparison tools remain in progressive disclosure.
Native session/CSRF/budget/idempotency rules remain authoritative. Late responses
cannot repopulate a closed dialog; session changes clear transient results.

The dossier is a reading surface, not a grid of widgets: question, actual
selected-investigation counts, claim/evidence blocks, entities/connections,
first-class SourceCard/SourceMetadata/SourcePreview, structured timeline, open
research paths and TransparencyPanel. Source usage is computed from saved evidence
links and deduplicated by claim. Publication dates and primary/secondary status
are explicitly unknown when the native capture does not establish them. Exact
quotes, locations, hashes, original links and contested history remain visible.
The source reader expands to full-screen on mobile. Counts do not pretend to
measure evidence completeness, truth, medical/legal accuracy or internet coverage.

The reusable Lens system derives state from an actual persisted in-flight step:
searching, reading or extracting. A 95-second expiry exceeds the native 90-second
operation budget; missing, future, completed, failed, queued, paused and stale
steps cannot keep an analysis animation active. Text communicates the same state.
Cross-reference, verification and synthesis states are reserved for corresponding
native capabilities, not simulated by a timer. Reduced motion uses a static Lens;
forced colors omit the optical decoration while retaining readable status.

Keyboard command/source dialogs preserve existing accessible primitives. Tablet
navigation collapses; mobile has a drawer, persistent Ask control, stacked
metrics and a full-screen source reader. Theme preference is device-local. Query
text, evidence and search results are never saved in localStorage.

## Validation and limits

Both products passed 77 automated client contracts, lint, strict types and final
Sites builds. Seven new behavior tests cover actual/stale/terminal Lens activity,
escaped accessible state text, true counts and source usage, unknown metadata,
global anonymous availability and recorded-action transparency. Existing private
routing, external query disclosure, CSRF, SSE, provenance, recovery and source-link
tests still pass. The core backlog smoke check passed; no API, model, schema or
provider configuration changed. All 121 files in each build were checked for the
configured provider key values with no matches.

Sixteen authored light/dark color pairs exceed WCAG AA's 4.5:1 normal-text ratio;
the calculation is retained in the release evidence. This is not browser-computed
or whole-page contrast certification. The existing local Pharma preview rendered
HTTP200; the foreground preview handoff was queued by the app. Browser interaction,
visual screenshots, professional accuracy and human accessibility acceptance are
not claimed. Exact custom-domain asset and route verification is recorded in the
release receipt after publication.

## Remaining work

The full dynamic dossier engine stays IN PROGRESS. Retained-original contribution
extraction is delivered in release 1.10; [workspace dossier teams](PRODUCT_TEAMS.md)
are delivered in 1.11, private active monitoring in 1.12 and outside-workspace
invitations in 1.13. Living public slugs/search and the shared public evidence
reader are delivered in 1.14 with exact production acceptance.
Material-change reopening and cross-investigation history are delivered within
scoped releases 1.15–1.17. Recurring web discovery, personal research updates and
whole-dossier retrieval are delivered in 1.18–1.21; their evidence and limits
remain separate from full-spec acceptance.
Native helveticlens.ch legacy screens should adopt the validated design foundation
incrementally. Keep every source/access boundary and preserve functional parity;
do not introduce a second UI framework or new data store for this migration.

## Exact production acceptance — 27 September 2026

Both existing public Sites projects published version 12 successfully:
Pharma main `2a10c11bc053bb958dd62a9ac0c0522519ca63a1` at 15:16:04 UTC and
Loyer main `cf6ce3134d5113b1e6f7c2ab5c583c0159e5522e` at 15:16:32  UTC.
Each custom domain passed 50 anonymous HTTP/auth/gateway/content checks and
39 exact emitted asset hashes. Global Ask and theme controls are present on
home, guide, public catalogue and following routes. Compiled shared tokens,
reduced-motion rules, metrics and source-reader styles are present. Both GitHub
CI runs completed successfully (36328796562 and 36328805234). Native functional
code remains the verified 1.8.1 baseline; this core change records the supplied
brief, implementation boundary and acceptance only.

[Exact release evidence](product-releases/2026-09-27-1.9.0.json) and
[authored contrast calculation](product-releases/2026-09-27-1.9.0-contrast.json).
The two-client foundation/reference-dossier slice is DONE within this scope;
full native-platform visual migration and dynamic-dossier acceptance stay open.

## Brandbook v1.0 update — 1.13

The owner supplied `docs/BRANDBOOK_V1.md` and the matching 18-page PDF on 27 September 2026. The Markdown is retained unchanged; both were reviewed. The newer brandbook controls palette, typography, H monogram, glass and motion where earlier visual guidance differs. The client shell now uses Carbon/Obsidian/Frost, a 1440px content limit, Inter-compatible neutral typography, structural 30px glass and one 560ms analysis transition. Dark is the initial theme; existing explicit light/system preferences remain available. Refraction appears only with actual investigation activity. Native platform-wide visual migration remains OPEN.

Brandbook client acceptance is recorded in [release 1.13](product-releases/2026-09-27-1.13.0.json): both public Sites 16,85 tests per client, seven checked contrast pairs, and exact production asset parity. This establishes the client shell and controls; native page-wide migration and human visual acceptance remain open.

## Living public research — 1.14

The public reader now reuses the existing findings, source previews, Lens, timeline
and transparency components, including anonymous server rendering. Typed public
search links to canonical dossier slugs and exact claim/source/entity anchors.
The same global Ask prepares a public question; explicit authorship and external
discovery consent precede submission. Signed owner publication enables this mode,
and changed publication revisions fence stale public findings. Brandbook tokens,
reduced motion and the original snapshots remain intact. Both clients pass 89
tests, lint, strict types and final builds. Both existing public Sites17 are verified: 80 HTTP checks and 47 exact served
assets per product. [Exact release receipt](product-releases/2026-09-27-1.14.0.json).
No browser or human visual acceptance is claimed.


## Ongoing private monitoring research — 1.16

Both clients now expose standing research settings, actual last-check/daily-usage
state and source-linked trigger history through the same Brandbook typography,
accessible controls and existing Lens. No animation runs merely because a policy
is enabled. Both99-test gates, builds and exact production Sites19 pass; each
origin has97 HTTP checks and47 exact assets. See
[acceptance and limits](PRODUCT_MONITORING_RESEARCH.md). Native page-wide migration,
watched-page triggers and remaining full-spec work remain IN PROGRESS.


Release 1.17 adds an opt-in saved-page scope to Keep this dossier current, readable
source readiness and paired earlier/newer excerpts with revision-pinned source
readers. Existing shared tokens, disclosure controls and DocumentHistory dialog
are reused in both products. The paired text stacks on mobile, quotations stay
escaped and no new Lens animation or evidence-quality metric is invented.
Validation and exact release acceptance remain tracked in
[watched-page research](PRODUCT_WATCHED_PAGE_RESEARCH.md).

Release 1.17 scoped production acceptance passes: both clients 101 tests, lint,
types/builds, exact Sites 20 origins with 98 HTTP checks and 47 exact assets each.
Native saved-page fixtures and source/corpus revocation cases pass. No browser
interaction or human visual acceptance is claimed. Full native migration remains
IN PROGRESS; see the linked watched-page release receipt.


## Shared product navigation and native identity — 1.22

The [shared navigation journey](PRODUCT_NAVIGATION.md) connects both products and
the native platform without transferring a question, dossier or unsaved work.
Both product command surfaces and sidebars retain their Brandbook themes. The
native H identity, neutral reading frame and structural glass sidebar are the
first bounded native visual migration; all nine directions remain directly
navigable. Existing native evidence pages and the full dark/light migration
remain open. Local checks pass; exact production acceptance is pending here.
