# Bounded query reformulation — 1.60

Scope recorded before code, 30 September 2026. COMPLETE within bounded scope; Core and both clients verified. MV2-002/020/024,
full architecture, live semantic quality and professional/human acceptance OPEN.

## Scope, dependencies and source readiness

New public exploratory episodes may try one alternative query in the same episode
when a completed, fully available search returned no candidates or all permitted
candidates were conclusively unrelated. Reuse the existing worker, branch state,
public planner model, relevance gate, source reader and all existing quotas.
No new episode, recurrence, source/provider, schema, permissions or user fields.
Keep the original question and branch query unchanged. Store the alternative as an
unconfirmed search hypothesis, with retained original retrieval and step receipts.
One reformulation attempt per episode including a failed/interrupted model attempt.

Missing/partial index outcomes, provider errors, omitted candidates, exclusions,
duplicates, unavailable gates, candidate limits, failed reads and exhausted budgets
are not evidence that query wording caused the problem. They cannot trigger this
recovery. Current exclusions are rechecked before and after the model. Only the
submitted public question and public planned questions/queries enter this request;
no private notes, files, source excerpts, raw errors or source-review comments.
Never repeat a normalized current/earlier query, invent facts, claim intent was
corrected or treat a snippet as evidence. Keep a final-briefing model reservation.

The alternate query uses normal actual search, gating, permitted acquisition and
exact-citation extraction. Original candidate/index accounting must survive. Show
confirmed current reformulation or alternate searching, plus a short saved outcome
and inspectable original/alternative wording in both readers, including history.
Inherited source/hash/access/ancestry and activity expiry boundaries still apply.

Dependencies/configured integrations are present. Use durable synthetic fixtures,
not paid/live research, private production data, new credentials or frozen 1.35/
1.37 validation. Source readiness does not establish search quality. Preserve
nine native Monitoring routes, Brandbook, Apache-2.0 and existing public Sites.

## Acceptance

- Both products: an unproductive search leads to one distinct query, actual gated
  source reading and exact cited briefing; original user intent stays unchanged.
- Empty and all-unrelated results are supported. Alternative failure or emptiness,
  null/duplicate output, all/partial/unknown index failures, exclusion, omission,
  candidate cap and unavailable relevance evaluations finish without a loop.
- Existing model/search/time budgets, pause/resume/cancel, interrupted/stale leases,
  old episodes and private/contribution/recurring paths preserve their contracts.
- Private canaries never enter the new model/search request or public projection;
  revoked evidence hides dependent summary. Retain honest original scope counts.
- Reader distinguishes a proposed query from an executed one, source captures from
  an answer, and history from an action. No extra polling, form or dashboard.
- Exact API lint, affected integration/regression and backlog invariant; both full
  client suites/lint/types/builds, protected-value and parity checks before push.
- Verify normal Core activation and exact current Sites artifacts; final English
  evidence and its activation retain unchanged client publication receipts.

## Implemented contract

`product_query_recovery.py` adds query-recovery/v1 only to new exploratory
episodes. The existing branch is reopened once after a completed fully available,
unproductive retrieval. A new durable reformulate step uses the configured public
planner model with only the original public question/query and prior planned
queries. Null, invalid, normalized duplicate or failed/interrupted proposals never
loop. Current exclusions are checked before and after that request.
Final dependency audit extends that boundary to every recorded source-triggered
prior public query: its source must still be permitted at the recorded hash before
and after reformulation. An excluded or changed trigger suppresses the proposal.
The focused hardening checks and exact native activation passed. No source
snippet, private evidence, note, provider error or review comment enters it.

The original question and branch query remain unchanged. A recorded alternative
controls the actual existing search/gate/read work; original candidate/index
outcomes and all step receipts survive. Later generated follow-ups cannot repeat
that normalized alternative. The existing model reservation also checks remaining
search/read/gate capacity before spending the reformulation request, and preserves
the final-brief reserve. Other execution, account quotas and access gates stay in
force. A human-authorized budget continuation may resume blocked work; absence of
a reply does not grant another episode or monitoring.

Both readers distinguish preparing a wording, proposed but unsearched wording,
completed/failed retrieval and retained captures. Original and alternative wording
are inspectable under existing scope details and labelled as unconfirmed. Actual
activity expires with its worker receipt; history makes no request. The existing
source/hash/access/ancestry guards hide dependent output. No schema or provider
configuration changed. Conservative eligibility declines recovery when index
coverage, omissions, candidate limits, exclusions or relevance decisions leave the
original result ambiguous; that broader research remains unfinished, not absent.

## Local and production acceptance

Thirty new durable cases passed (21 initial cases, six further fences and three
source-dependency cases);
three final affected budget retests overlap that count. Thirty-two existing
scope/activity/backlog cases passed. Fifty-six existing worker/exploration/source-recovery regression cases passed,
for 118 distinct Core cases. Four additional final recovery cases after the
source-dependency hardening overlap those totals. Initial production and final native hardening activations are verified below. Each client passed
302 tests, lint, types and its production build. Exact API lint passed after
import/test formatting cleanup. Completed 1.22 overview archived verbatim into
linked release history; the 512 KiB guard is unchanged.
Synthetic cases establish mechanics and privacy, not live semantic accuracy.


## Initial verified production activation

Core `2b90aa3d0dae5d33ce19d3af1ed140cc02549901` activated at
2026-09-30T01:17:55+00:00. Legal `d874cb50d05cecfd892253d14410327a9c42e3a2`
and Pharma `7e48a1077af755d8021e5ef23515c032338bfb9f` are active in existing
public Sites 59, respectively since 2026-09-30T01:14:49.303183+00:00 and
2026-09-30T01:14:57.985063+00:00. Fifty-one exact native module hashes,
current schema, five running containers and nine routes were verified. Each
client passed 47 exact deployed-asset comparisons and 51 HTTP/access checks.

The [frozen initial receipt](product-releases/2026-09-30-1.60-query-recovery.json)
has SHA256 `2c64de71253d4a342d757c0dc923c2684439c18154e4e08f33e7dee8f416b259`.
Packaging initially lacked the child Node PATH; corrected packaging reused the
validated builds without source changes. No private production dossier, paid
inference, browser QA or frozen validation was used. Final review added current
rights/hash validation for source-triggered prior queries, before/after the new
model request. Three new durable cases and four affected recovery retests passed;
its normal native activation is now verified below.
The clients are unchanged and must not be republished for this Core hardening.


## Verified source-dependency hardening

Core `a2126ce92f617cb2e87c0dbcda607b61263bb4ce` activated as
`git-a2126ce92f61` at 2026-09-30T01:26:31+00:00.
The [hardening receipt](product-releases/2026-09-30-1.60-query-dependencies.json)
verifies 51 exact native modules, schema, nine routes, main alignment and both
product homes. It reuses the frozen exact Sites 59 client receipt; unchanged
clients were not republished. SHA256 `adaa215449384d6f14b7e832f1d8e04ccc46b1ef1d70edb42f23ef480dddf4a0`.

All 118 distinct Core cases and 302 client cases/lint/types/builds each passed.
Additional affected reruns overlap those counts. Current permission/version checks
prevent a recorded revoked source-triggered question from entering reformulation
or launching its result. Protected-value and shared-reader parity checks passed.
Final English evidence follows normal native activation without client changes.
Full architecture, live semantic quality and professional/human acceptance remain
OPEN. Next: assess usefulness of actually read passages through the existing
extraction request, with exact evidence, current rights and unchanged budgets;
no live quality or new behavior is claimed by that read-only audit.
