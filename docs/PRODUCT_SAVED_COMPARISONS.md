# Saved comparison clarity and selection safety

Status: DONE — scoped production release 1.26 under MV2-002/020/024. Scope,
dependencies, source readiness and acceptance were recorded before implementation.
The broader MV2 tasks and complete dynamic/visual specifications remain IN PROGRESS.

The native comparison workspace distinguishes an unsaved baseline choice from
the persisted comparison shown below it. Ordinary background reads and passage or
candidate pagination preserve the draft. A changed event, event version or saved
revision requires explicitly returning to the current saved choice before another
write. The actual write boundary repeats the same guard and retains existing
organization authority, optimistic concurrency and late-session response fences.

Successful saves use the server's exact revision/comparison receipt. Earlier
results stay hidden until the current read acknowledges that receipt or a newer
choice. Identical saves may preserve a revision; the reader handles that case
without waiting for a revision that will never arrive. Failed current reads hide
previously retained comparison text, and unavailable or revoked comparisons do
not render saved-pair summaries or quotations. A successful write remains a
successful write even if its following read fails.

The persisted pair has an actual material-change count, capture times, full version
identities and exact saved-source links. Unavailable counts remain different from
zero. Literal earlier/newer passages use neutral surfaces, 16/26 body type and a
75-character maximum reading measure. Five native locale dictionaries cover the
new copy. Narrow screens stack the pair; disclosure controls retain focus and
44-pixel targets. Existing controls, registry return, pagination and source language
are retained. Text comparison is not a finding or legal-consequence assessment.

In Pharma and Loyer, watched-page change readers show both full retained-text
lengths, capture timestamps and progressive full version, evidence-revision and
SHA-256 details. Counts describe retained texts, not bounded excerpts. Partial
previews remain explicit. Earlier/newer reader actions open each exact version and
revision; unavailable positions do not produce a misleading action. The current
capture timestamp is the watch trigger's version-created timestamp, not a document
publication or effective date. No new API payload, request, schema or provider is
needed: the existing authorized change payload already contains these fields.

## Verification and limits

Focused behavior checks exercise draft preservation, conflict/write guards,
server-receipt acknowledgement including unchanged revisions, exact source and
passage references, five-locale server rendering, unknown versus zero, escaped
quotations, partial-preview limits and actual revision-pinned reader callbacks.
The full native frontend/localization/typecheck tree passes 403 cases, including
12 new comparison behavior/rendering cases. Both clients pass 147 tests each
(five new), lint and strict types. Native Next and both portable Sites production
builds pass. The exact API Ruff gate, current backlog smoke and protected-value
source/build scan pass. All 71 affected API contract cases pass, covering complete native pairs,
concurrent choices, authorization/CSRF/viewers, revoked evidence, watched-page
captures and the backlog smoke. Exact production verification passes as recorded below.

No browser/preview/DOM/screenshot QA, production private records, paid provider
probes, new registrations/keys or outgoing messages are used in this background
cycle. Human visual, language and professional acceptance remains open. Provider,
model, source-rights, publication and delivery contracts are unchanged. All nine
Monitoring directions and existing deferred work remain intact.


## Exact production acceptance — 28 September 2026

Native implementation e12898b3d23ba13d2780ae67de3f844e80e5e156 was committed, immediately pushed and
activated normally at 2026-09-28T08:24:31+00:00. Exact public readiness and the
healthy immutable web image agree on git-e12898b3d23b. Saved-comparison,
source-reader, command, navigation and theme bundles include 47 matching
served assets and pass 54 HTTP checks, including anonymous denial of native
comparison/candidate and private source metadata. All nine directions, five
comparison locales, the H identity and early themes remain present. This is
programmatic evidence, not browser QA.

Pharma 1b7370b9077e2f5b18ccad008986bb8548875c53 and Loyer
0f6cf83054777e5345cd08af82c27cd80ecc1edd were immediately pushed to GitHub main and the existing
Sites source repositories. Both exact archive-backed Sites 29 publications
succeeded. All 136 files per archive match the validated local build; transport
and Sites-reported hashes remain separate. Both custom origins pass 131 HTTP,
auth, guide and compiled-contract checks and 47 exact assets each. Both exact
GitHub CI runs passed.

Runtime proof matches 60 source modules, including native comparison views,
selection writes and product watched-page capture, unchanged migration
06d495bef125, current-rights queries, four native runtimes, five scheduler modules
and the minute cadence. Laya and pinned local E5 remain healthy. Model/parser
probes use synthetic local input only. No API, schema, provider, model, key,
source-rights, publication or delivery contract changed.

The [sanitized release receipt](product-releases/2026-09-28-1.26.0.json) records
source, archives, activation and exact verification. This scoped comparison
journey is DONE; complete dynamic/visual specifications, broader MV2-002/020/024
and human/professional acceptance remain IN PROGRESS. The hourly heartbeat stays
ACTIVE; deferred work remains deferred.
