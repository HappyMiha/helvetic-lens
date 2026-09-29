# Read the dossier before its tools — 1.49

Status: scoped implementation DONE; production clients verified on 29 September 2026.
Scope recorded before code. Full target and professional/human acceptance remain OPEN.
MV2-002/020/024; preserves the owner's one-question product priority.

## Outcome and dependencies

The opening Dossier chapter shows retained research before metadata and tools:
what the latest investigation is doing, the most recent completed evidence update,
cited machine findings, exact source excerpts and source checks needing attention.
A new running/failed/empty investigation must not erase the previous source-bearing
completion. Every excerpt and finding opens the existing investigation/source/claim
reader. No form, new inference, acquisition, subscription, publication or generated
summary is introduced merely by opening the dossier.

Reuse current GET investigations, private follow/updates, dossier coverage,
ResourceReader/useResource, research navigation, quote provenance and coverage
helpers in both clients. No Core API, database, migration or provider change.
Private follow/updates excludes unchanged captures, failed/unfinished research and
withdrawn evidence; it reads without creating a subscription or acknowledging it.
The latest investigation state and retained update are separate dated observations.

## Acceptance

- The overview starts with a compact document section, before optional fields.
  New one-question starts land on this reading overview instead of the detailed
  research toolbox. Explicit investigation/source/claim deep links still open the
  detailed reader. Creation, advanced research, history and nine native routes remain intact. No browser or preview this cycle.
- Distinguish loading, unavailable, not started, queued/running, paused, failed,
  cancelled and finished. Finished is not complete source coverage or truth.
- Show the latest visible completed source-bearing update (bounded API samples),
  even if newer research is running/failed/unchanged. Label machine findings as
  such; do not infer current human acceptance or suppress contradictory states.
  Findings without a citation are identified as needing evidence, not quoted as
  supported. Source excerpts are separate from findings: a source sample is not
  falsely asserted to be that finding's exact supporting passage.
- Exact source/claim links reuse the existing saved readers. React escapes text;
  URLs are not constructed from provider text. Source timestamps and excerpt
  truncation remain visible. Indicate limited displayed samples and prior updates.
- Coverage attention uses existing page/pack status rules. Healthy saved collection
  is not a whole-dossier check; empty sources are not complete coverage. Show a
  concise limitation and link to the existing source coverage view.
- All reads are GET-only. Refresh/polling does not start research or mark updates
  read. Any failed access/read hides retained content until recovery; late responses
  from a prior dossier/session cannot restore it. Use current resource ownership.
- Meaningful render/reconciler tests cover source/citation links, separate AI/source
  text, failed latest research with older evidence, empty/incomplete coverage,
  read errors/recovery, session and dossier transitions, late responses and no writes.
- Both-client full tests/lint/types/build, Core backlog invariant, shared-source and
  protected-value checks; immediately push tested main and publish exact existing
  Sites artifacts. Observe normal Core documentation activation and verify current
  native/code/route identity plus exact public client assets and access boundaries.

## Limits

This is a deterministic reader of existing bounded records, not a new synthesized
answer, whole-corpus summary, calibrated importance score or review decision.
No new live source, paid model, private production or professional/human acceptance
claim. Source-request projection, automatic subject-to-inference context and the
full target remain open. ai.helveticlens.ch remains outside the agreed client scope.

## Verified implementation and publication

Both clients now render the reading summary first, retaining prior completed
source-bearing evidence separately from newer work. Exact claim/source actions,
separate source quotation, recorded AI assessment, contradiction/update counts,
limited samples and existing coverage attention are tested. Uncited text is not
retold as supported. Refresh and polling only read existing data; read/access
failure hides saved content and current session/dossier ownership rejects late
responses. One-question creation lands on the overview; explicit research links
still open the detailed reader. Optional metadata and tools remain available.

The seven new meaningful render/reconciler cases cover retained evidence after a
new failure; citations and source/AI distinction; unsafe text/URLs; empty/finished
coverage; lifecycle labels; access failure and recovery; and stale/foreign dossier
or session data. Both complete client suites pass 246 tests, lint, types and exact
Sites build. Protected-value and shared-source parity checks pass. No API runtime,
schema, source connector, model call or provider configuration changed.

Published main: Legal `c495158e98896ac86b809fec648ecf19a9c53f51`,
Pharma `eefd8cfdf62967c3f3c218d7169fbe566d666253`. Existing public Sites 48
activated at 13:23:13Z and 13:23:41Z respectively. Exact production verification
matches 47 assets and 48 HTTP/access checks per client, including the new reader's
private GET boundaries. Current native Core `git-2abb039f4980` matches 42 runtime
modules, existing schema/DomainPacks, five containers and all nine native routes.
No browser, authenticated production dossier or inference probe was used.

[Immutable publication evidence](product-releases/2026-09-29-1.49-dossier-reading.json)
records exact source, deployment, artifacts, checks and limits. This documentation
commit still requires its normal Core activation; the parent cycle checkpoint
will record that final activation without republishing unchanged clients.
