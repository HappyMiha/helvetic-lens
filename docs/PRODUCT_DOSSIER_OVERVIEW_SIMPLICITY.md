# One coherent dossier overview — 1.50

Status: scoped implementation DONE; production clients verified on 29 September 2026.
Scope recorded before code; full architecture and human acceptance remain OPEN.
MV2-002/020/024; follows the owner's one-question UX priority and verified 1.49.

## Outcome, dependencies and source readiness

Keep saved research as the first reading surface. Remove the old empty cards
which send a question-monitoring reader to research already visible above.
Topic-match evidence and investigation evidence remain distinct collections.
Existing configured topics and history become optional disclosure sections;
actual topic matches and read failures remain visible with their current actions.
Recent activity is a folded, bounded journal below the document, not a competing
sidebar. Preserve the established typography, themes and document reading width.

Reuse the existing dossier payload, topic matches request, Evidence renderer,
current navigation, permission flags and retry handler. No API/schema/provider,
monitoring/consent, ingestion, inference, source readiness or access change.
Read-only code inspection found this overlap; no browser or private production
inspection is used in this background stage. ai.helveticlens.ch is out of scope.

## Acceptance

- A one-question dossier with no configured topics or topic matches gets no
  duplicate empty source card. Its 1.49 research reader still owns research state.
- Topic-match loading and failure remain visible even for that dossier. A failure
  never exposes retained match children. Retry uses the existing handler.
- Real topic matches remain visible whether or not topics still exist, with the
  same source/evidence and authorized review actions. No automatic read/write.
- Configured topics remain in a collapsed native details element with their
  goals, concepts and revision history. Empty configured-topic results are
  qualified as topic matches, never absence of research or complete coverage.
- Classic draft setup remains available only with configuration permission;
  active classic empty results retain the incomplete-coverage qualification.
- Recent activity preserves authored labels, actor and date; show only the same
  bounded eight entries and label the sample. It is closed initially and escapes
  untrusted text. Do not remove records or merge AI findings with human comments.
- Focused render/action checks prove these distinct states and navigation/retry
  callbacks. Both full client tests, lint, types and exact builds must pass.
- Run backlog invariant and protected-value/shared-source checks; push main and
  publish exact changed clients to the existing Sites projects. Verify production
  assets/access, then commit English receipt once and observe normal Core docs
  activation with final exact native/repository checks. No repeated UI publish.

## Boundaries

This is a presentation improvement, not new inference, automatic interpretation
of optional metadata, complete coverage or professional/human acceptance.
Full architecture, source-request projection and source readiness remain OPEN.

## Verified behavior and publication

The overview keeps Research so far first. DossierTopicOverview renders existing
source-match records independently from research evidence, preserves loading/read
failures and retries, and omits the duplicate empty block for a question-only
dossier after a successful empty read. Configured topics retain goals, concepts
and revision history in a closed disclosure. Real matches remain visible even
without configured topics, using the unchanged source/review renderer and current
permission condition. Classic draft setup and active-source limitations remain.
DossierRecentActivity retains the same eight-entry sample, authors and dates,
labels that sample and starts closed. All content uses existing escaped rendering.

Four new render/action cases cover no-result versus load/failure/recovery, exact
real match records, closed topic history and classic setup permissions, and
bounded escaped human/AI activity. Two existing complete-dossier tests now assert
the new reading flow instead of the removed duplicate prompts. Both clients pass
250 tests, lint, types and exact builds. Protected-value and shared-source parity
checks pass. No API, schema, acquisition, inference or monitoring state changed.

Published main: Legal `ec5143e45f1d96debc6736a7afed50de366b312d`,
Pharma `333d202b2d27535981ec23b6006138e37814cdc9`. Existing public Sites 49
activated at 14:15:02Z and 14:15:31Z. Each serves 47 exact matching assets and passes
48 HTTP/access checks, with the updated guide and overview code verified.
Current Core `git-4116f92e8ac6` matches 42 modules, unchanged schema/DomainPacks,
five containers and all nine native Monitoring routes. No browser, private
production dossier or paid inference probe was used.

[Immutable release evidence](product-releases/2026-09-29-1.50-overview-simplicity.json)
records source, artifacts, access checks and limits. The parent cycle checkpoint
will record normal activation of this documentation commit and the final exact
native/repository checks without republishing the unchanged clients.
