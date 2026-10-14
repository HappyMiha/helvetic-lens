# Shared feeds and dossier monitoring

## Scope recorded before implementation — 14 October 2026

Scoped MV2-002/011/020/021/023/024 continuation. The owner confirmed reusable
monitoring feeds inside Helvetic Lens Legal and Pharma. The existing LegalFeed
repository and running service must remain unchanged. Reuse its useful collection
mechanisms in shared Core; do not migrate its accounts, data, domains or schedules.

A feed independently collects and retains new or changed source material and can
be used without a dossier. Dossiers attach existing feeds or create feeds from an
explicit research question and selected public sources. One feed can serve multiple
dossiers; collection happens once, while each dossier independently evaluates impact
against its own research question. Dossier monitoring remains a visible capability.
Creating a dossier from a feed connects the entire saved history and future updates.
The feed never replaces independent dossier discovery or full-document analysis.

Dependencies: shared identity and dossier access, durable jobs and scheduler,
direct-source and replaceable broad-web adapters, retained source documents,
existing investigation/continuation engine, personal notifications, shared three
dossier account allowance, and both existing product clients. Source readiness is
limited to available public catalogues, explicitly supplied public URLs and the
configured web-search channel. Failures and partial reads must remain visible.

Acceptance:

- Standalone feed creation, collection, saved history, pause/resume and useful
  updates work without creating a hidden dossier or consuming dossier allowance.
- Existing/create-feed actions work in a dossier; feed-to-dossier creation uses
  normal allowance admission and retains the automatic link.
- All feed history is durably admitted for research, including more than one
  retrieval page; resumable processing cannot silently drop the older tail.
- Source changes are immutable versions, repeated checks do not duplicate unchanged
  bodies, and one feed supplies independently permission-checked dossier links.
- Detach, pause, deletion/revocation and stale revisions are respected by workers;
  idempotent retries do not duplicate feeds, dossiers, collections or imports.
- Long documents preserve originals and reading continuation; snippets are not
  represented as fully read documents. Collection and semantic relevance are
  separate from the dossier's deep analysis.
- Clear loading/empty/failure/progress states, source links and saved outcomes in
  both clients; existing dossier navigation and research remain usable.
- Required affected Core tests, Ruff, backlog guard and client test/lint/type/build
  gates precede complete main publication and verified production activation.

## Delivery status

Collection/linking and the owner's semantic-search refinement are implemented and
locally validated. Production activation is recorded separately after publishing.
The main user path is one question and a
Watch action; source choices, names and diagnostics are optional/collapsed. Existing
dossier questions are reused with visible public-search scope, and can be changed.

Validation evidence (14 October 2026):

- 13 API scenarios, including 123-version history admission, shared allowance,
  owner/tenant isolation, explicit public questions, private-question exclusion,
  latest-first history, failed-work recovery and current revision fences.
- Native worker: retained A→B→A versions produce a cited dossier answer; a later
  version starts through the scheduler, reuses prior public context, completes a
  second cited answer, and preserves the first. Full source reading is exercised.
- 14 collector scenarios: full original continuation, RSS/Atom archive pages,
  independent source failures, exact-byte retries, crash-tail recovery, unchanged
  deduplication, stale leases, paused/revoked access and retained original cleanup.
- 6 following/schema scenarios: feed-only creation consumes no dossier allowance,
  read markers preserve newer arrivals, preference retries are idempotent, current
  access is checked inside writes, additive upgrade and nonempty downgrade refusal.
  The schema round-trip also passed again after the pinned-question column was added.
- 25 existing personal-research regression cases, the mandatory backlog guard,
  2 maintenance regressions and full API Ruff passed.

The initial collection implementation made no model calls. The semantic extension
adds query planning and Laya relevance checks. Linked dossiers retain independent discovery,
full-document analysis, citations and normal personal research notifications.
Feed-only notifications are in-app unread updates. Intentional pause/cancel and
failed research require explicit recovery before newer history can bypass them.

The existing accepted production dossiers were not replayed for verification.
LegalFeed remains unchanged. No production fixtures or outgoing test email were
created. Client gates and native deployment receipts are captured with the release.

## Semantic feed refinement — owner instruction, 14 October 2026

Scope: a feed continuously discovers information by meaning, while a dossier
performs deeper investigation. Keep creation to one question and Watch; add a
collapsed Refine search action, useful/not-useful feedback, and explicit learning
from the dossier's authorized public question, cited findings and gaps. This is
context-guided search refinement, not model weight training.

Dependencies: existing research gateway for semantic query planning, local Laya
for typed relevance judgments, configured replaceable web search and independent
direct-source connectors. Web indexes cannot promise exhaustive internet coverage.
Selected public sources augment broad discovery. Preserve source failures and
model unavailability as visible states rather than empty successful results.

Acceptance before publication:

- Meaning, related concepts and multilingual query variants drive discovery;
  literal word overlap never impersonates semantic relevance when Laya is absent.
- Relevance checks cover retained originals with resumable progress; unrelated
  classification cannot be inferred from only the first part of a long document.
- Precision edits and feedback revise future discovery and reassess retained
  sources without rewriting original versions. Assessment history is separate.
- Private notes and contribution questions never enter public-search context;
  learned context remains pinned to current link/access/revision authority.
- Relevant and pending/uncertain material have clear reader states; unrelated
  material remains accessible. Every retained version stays available to a linked
  dossier, whose independent question determines its own relevance and impact.
- Both clients retain the three simple actions and receive behavioral API,
  collector, migration and client verification before publication.
- Watch changes previews monitoring from the completed public research and enables
  the feed, link and reviewed context together. If completed public research is
  unavailable, show an honest question-only proposal. Proposal reads do not call
  models. Existing-feed attachment remains a simple alternative.

Implementation review found the installed local Laya service accepts at most
4,000 characters of serialized state and 20,000 request bytes. Source portions
are sized to its actual request envelope; a compact conceptual scope lives in
topic-specific decision criteria. Continuation retains the exact source position,
including for non-ASCII material. This is a technical per-request constraint, not
a total research budget or permission to discard a document's remaining text.

Final local validation:

- 15 collector and 9 semantic-worker scenarios: multilingual query cursors, full
  originals, relevance in the document tail, independent source/model failures,
  exact-byte recovery after pause/resume and refinement without duplicate versions.
- 13 feed API/native investigation scenarios, 7 semantic API/proposal scenarios,
  and 7 following/schema scenarios passed. Public context preview is a saved read;
  application is fingerprint-bound and atomic. Unrelated history remains available
  to independent dossier questions. Mixed/private inputs and revoked access cannot
  leak through learned public-search context.
- Six read-only local Laya probes verified the actual request contract, including
  Unicode request boundaries. English/Ukrainian paraphrases were included, a
  software homonym was excluded, and contrary/German evidence remained visible as
  uncertain. This small operational check is not a measured accuracy benchmark.
- Legal and Pharma each passed all 595 client tests, affected lint/type checks and
  production builds. Final Core Ruff, migration/downgrade and backlog guards passed.

Publication prepared as clients 1.110.0 (Legal `9f35165705f9`, Pharma
`e91040b36d59`). Production activation is blocked by an independently observed
host NVIDIA driver/library mismatch: loaded 580.173.02, installed 580.178.04,
missing persistence-daemon socket and stale GPU container specification. Existing
data and model routes are preserved; this feature has not been claimed active.
