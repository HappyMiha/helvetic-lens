# Useful orientation while research continues — 1.52

Scope recorded before implementation on 29 September 2026. MV2-002/020/024 remain
IN PROGRESS; this slice is DONE within the verified scope below. Full architecture, live-provider semantic
quality and professional/human acceptance remain OPEN.

## Scope and dependencies

Extend the existing research-first episode with one early source-backed orientation
before remaining search/extraction finishes. After at least two eligible captured
public documents, the same durable worker may spend one model request within the
existing cumulative episode budget. Keep capacity for the final briefing and
further research; a missing/invalid early result must not stop useful work.

The saved, versioned early checkpoint contains one to three evidence-linked
possible interpretations, each with an exact passage, an explicit tentative or
questioned status, and bounded unresolved questions. It does not rewrite the
user's question, claim finality, trigger clarification automatically or enable
monitoring. The final briefing rechecks the earlier working interpretations against
all currently eligible sources; the earlier checkpoint remains inspectable.

Both clients show this calm reading surface while work continues, separate from
source quotations and the actual journal. Pause allows a corrected public question
and a new episode without losing the old evidence. Verify this works before any briefing exists by using the fresh checkpoint
returned by pause, never a stale revision from before the action. Historical
readers retain the early snapshot; access failure/exclusion hides derived text.

Reuse Investigation.research_state, branch leases/generation, request receipts,
current source exclusions, exact citation validation and current model/providers.
No new data store, migration, external credential or unbounded background task.
Existing final briefs, legacy dossiers and explicitly consented monitoring remain
compatible. Keep all nine native Monitoring routes and the frozen studies intact.

## Source readiness

Use only public sources already captured through the existing permitted search and
reader. At least two eligible source snapshots and remaining request/time capacity
are required. Search snippets, private notes/files and excluded sources cannot
enter this orientation or its later context. Tests use fictional scripted adapters
through the real worker, not paid production probes or a quality benchmark.

## Acceptance

- A real worker yields one persisted cited early orientation while the run is
  active and additional research remains; final briefing and history follow.
- No early inference without sufficient eligible evidence/capacity; final model
  reserve remains available and totals stay within existing budgets.
- Invalid quotes, changed/excluded sources, provider failure and interrupted work
  leave honest visible status and let remaining research proceed without retries.
- Pause/generation/session fences discard stale results. A corrected public question
  can continue from the fresh paused checkpoint before any final brief; retries
  create one episode and stale pre-pause revisions remain rejected.
- Final synthesis receives only a currently eligible early checkpoint; private or
  subsequently excluded dependencies cannot leak through summaries or history.
- Both clients distinguish tentative/contradicted interpretation from exact source
  words, preserve the initial question, keep the earlier snapshot after completion,
  and offer pause/correction without automatic recurrence or extra setup fields.
- Required Core affected tests/lint/backlog invariant, both client tests/lint/types/
  build and exact production activation are recorded before this slice is DONE.

## Implementation and compatibility

The existing exploration contract has an additive `orientation/v1` checkpoint.
An `orient` branch runs once at elevated priority after two eligible, nonduplicate
captured public documents. It is scheduled only with at least three model requests
and 45 active seconds left. Its request has a 20-second cap within the existing
360-second/16-model-call episode limits; one further work request and the final
brief request remain available when it is scheduled. This is a bound, not a promise
of exact latency or final semantic quality.

Exact source quotations validate before any interpretation is saved. All supplied
source identities/hashes become dependencies of new early and final briefings,
including inputs not directly quoted in their displayed text. Current exclusions
or changed snapshots invalidate the whole derived checkpoint on read or before
commit. Older final briefings retain their existing citation-based compatibility
checks. Optional failures/interruption are visible and are not automatically retried.
Provider-route metadata is retained for failed inference as well as valid results.

The final briefing can inspect the still-eligible early checkpoint in the same
run. A paused correction starts from the explicitly corrected public question;
the unconfirmed early interpretation is retained for reading, not promoted to the
new user's intent. Pause already advances the checkpoint revision; correction uses that newly
returned revision, including when there was no earlier briefing.
Existing current-access, latest-run, generation and idempotency fences still apply.
No database migration or new API route is required.

Both clients present the tentative early meanings and exact passages as separate
reading elements. Final readers fold the earlier checkpoint into history. Reading
or polling never chooses a direction or enables monitoring. Initial questions,
source quotes, substantive clarifications and explicit later recurrence retain the
1.51 behavior. Four added interaction checks per client passed; the complete 259
client tests, lint, typecheck and exact production build passed for both products.
Thirty distinct affected Core checks passed: 21 exploration/early-orientation cases
and nine legacy worker/iterative/start/backlog checks. Four selected cases were rerun
after correcting two stale pre-pause test fixtures and retaining failed model-route
metadata; those four overlap the 21 cases and are not additional coverage. Existing
revision validation was preserved. Exact API lint and protected-value/client-parity
checks passed. Exact production activation is verified below; no live semantic, browser or
professional acceptance is claimed.

## Verified production activation

Core `bd324ab07f3c2888cb7133b311d45d6a180b7846` activated as
`git-bd324ab07f3c` at `2026-09-29T16:07:55+00:00`.
Legal `623b6e6be62272e88837bfcee7584774784c721e` and Pharma
`f082e8d2093f6f1c4572c5559eee89e63897f689` are published as version 51
in their existing public Sites, with the same exact sources in both GitHub main
and the Sites source repositories.

[Production receipt](product-releases/2026-09-29-1.52-early-orientation.json):
45 matching native module hashes, unchanged schema/packs, five healthy containers
and nine native Monitoring routes. Each client passed 47 exact asset comparisons
and 49 HTTP/auth/origin checks. All three development repositories were clean
and aligned to origin/main. Frozen study validation remains unopened.

Receipt SHA256: `ef00b8e81fed8d1d53bab00bb7f668d7ba1847bbd6b9a328dfa0ff0e92c4c07c`.

These checks establish the deployed mechanics, source provenance, bounds and
access behavior. They do not establish live interpretation accuracy, clinical
or legal correctness, browser usability or professional/human acceptance. The
full architecture remains OPEN. Next audit: explicit, cited explanation of how
later evidence revised or left unresolved an early working interpretation.
