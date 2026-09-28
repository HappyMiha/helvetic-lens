# Readable dossier — release 1.30

Status: DONE within the verified 1.30 implementation and release scope.
Owner priority recorded on 28 September 2026 before code. Human usability and
broader parent acceptance remain open.
This UX outcome precedes further target-architecture implementation.

## Outcome

Opening a dossier should feel like opening an understandable working document.
Separate the product navigation and controls from the dossier, human discussion,
AI interpretation, research process and original source material. The current
private screen puts contribution, investigation and automation panels before a
collapsed eight-tab tools area. Replace that ordering with a calm dossier cover,
contents and a readable opening chapter; make other activities explicit chapters.

## Scope and dependencies

MV2-002/020/024 contribution on the existing Pharma and Legal clients. Preserve
Brandbook v1.0, dark/light/system preferences, existing shared API, all source
rights, roles, publication decisions and exact source links. No new schema,
source adapter, paid inference, synthetic findings or changes to monitoring
semantics. AI output must retain uncertainty and never imply human acceptance.
Source readiness is unchanged. Use existing UI primitives and common components.

## Acceptance

1. The default private dossier opens as a document with its purpose, direction,
   scope and real saved material. No contribution form, large metrics, research
   console or schedule configuration competes with the opening page.
2. Contents make dossier reading, AI research, sources/files, human discussion,
   actions, monitoring and sharing discoverable. Secondary controls appear in
   their relevant area. Every current capability stays reachable.
3. Human authorship, AI interpretation and literal source excerpts are labelled
   in words and distinguished structurally, not only by colour. Status, missing
   evidence, citation targets and source provenance remain honest and inspectable.
4. Deep links to questions, sources, investigations and quoted findings open the
   correct section. Global Ask still targets the active dossier even when the
   research section is not visible; asynchronous results remain permission fenced.
5. Draft, empty, loading, failure, viewer/editor and narrow/text-enlarged layouts
   remain usable. Reuse accessible tab/action primitives and current themes;
   preserve mounted research state while changing the reading section.
6. Meaningful rendered and navigation checks, both complete client test/lint/type
   gates and Sites builds pass. Push both tested main sources, publish existing
   Sites projects, verify exact live assets and access boundaries, then record
   scoped acceptance. Full architecture and human usability acceptance stay open.

## Visual thesis

A calm editorial dossier on a distinct reading surface, with a numbered contents
margin and generous typographic hierarchy. Discussion reads as attributed human
conversation; research carries an explicit AI label; source quotations have their
own document treatment and origin. The surrounding controls use a quieter
workspace treatment. No decorative imagery or simulated document content.

## Evidence

Both products now open on a distinct document surface with the saved question,
direction, audience, topics, latest saved matches and activity. A seven-chapter
contents rail separates Dossier, AI research, Sources & files, Discussion,
Actions, Monitoring and Sharing. Small screens place the scrollable contents
above the document. Existing theme tokens are retained. Print/export are in the
quiet options menu outside the document; automation and contribution forms no
longer precede the opening page.

Discussion keeps attributed questions/replies and the team notebook. Research
keeps the existing durable engine, saved-evidence search, material review and
explicit refinement. The research panel remains mounted while hidden so global
Ask continues to target this dossier; commands reveal the relevant chapter.
Saved source/question/research navigation chooses its chapter. Trigger links
reveal Monitoring, wait for their existing target, and focus it. The shared Tabs
wrapper now forwards its existing orientation prop to Base UI as well as styling,
so keyboard semantics agree with the vertical desktop contents.

Machine findings say “AI interpretation”; literal blockquotes say “Original
source excerpt” and retain locator and source anchors. Captured source previews
also label their origin. Loading is distinct from a successful empty response;
older requests cannot complete a newer match load. Draft setup, review status,
source limits, role checks and explicit publication stay with the existing API.
The public product guide explains the new chapters and relocated controls.

Verified evidence is retained in
[the 1.30 receipt](product-releases/2026-09-28-1.30.0.json):

- Pharma main `d5a9737a95c935cccced1d59426be2f46693777c` and Legal main
  `dad35bef7fc4380e69c1c7392c9904f60056c957`, immediately pushed after commit.
- Each client: 168 tests, lint, typecheck and production Sites build passed.
  Four new rendered tests exercise default reading/hidden research, source and
  question deep links, draft/older metadata and exact AI/source separation.
  The actual tab markup has vertical orientation; both complete regressions pass.
- Ten common client files are byte-identical. Protected-value scans and Git diff
  checks passed. Backlog invariant passed (one smoke check). No API changed.
- Both existing public Sites projects published version 33 successfully on
  28 September. Every emitted product static asset (47 each) matches its validated
  build by SHA-256. Each custom origin passed 27 HTTP/guide/auth/isolation checks.
- Unchanged Core `git-b72a4902df26` remained ready; five runtime module hashes,
  five expected containers and all nine navigation directions were verified.
  The retired public Loyer hostname remained unavailable and its DNS absent.

Production verification is read-only and anonymous. It does not claim a browser
interaction pass, screen-reader audit, authenticated workflow pass or human
usability acceptance. No private record or paid inference was used. The full
public dossier layout, localization and broader target architecture remain open.
Normal activation of this documentation commit is recorded in the local cycle
checkpoint; client publication does not depend on that unchanged application.
