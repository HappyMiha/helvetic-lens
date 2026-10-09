# Useful research context and intentional refinements

## Scope before implementation — 9 October 2026

MV2-020/021/023 usability repair. The owner demonstrated an all-optional subject
form whose empty save changes the timestamp/revision/history but neither research
nor monitoring. The adjacent template chooser similarly stores guidance only.
Dependencies: existing checked exploration/early understanding, natural research
reply with durable idempotency/recovery and privacy disclosure, legacy context
records, authorization, both product readers. Existing source availability only.

Replace the dead configuration path with a clear current question and the system's
available, labelled understanding from saved research. One natural-language
refinement previews the exact next public research question and starts the existing
continuation path, preserving earlier findings. No silent transfer of private
subject fields into external search, invented AI understanding, extra model calls
on page open or independent research queue. Hide the ineffective template chooser
from this path; preserve existing saved annotations/history under explicit private
reference details. Empty initial and normalized unchanged metadata writes must not
change revision/time/history; intentional clearing of previously populated data is
still a real change. Client must also prevent no-op saves.

Acceptance: current/early/absent understanding shown honestly; one clear refinement
input and meaningful submit, empty/unchanged input blocked; exact question shown
before submit; normal continuation/recovery/previous answer retained; denied or
changed access never revives old context. Metadata privacy, no-op equality, conflict,
exact replay and real clearing tested. Required Core affected tests/Ruff/backlog
and both client test/lint/typecheck/production build gates; verified main push and
existing product deployments. Do not restart or duplicate active owner research.

## Implemented

The dossier reader uses the existing exploration continuation endpoint, with one
plain-language editor and exact next-question preview. Duplicate questions are
blocked in the editor; deliberate continuation of the broad research remains
available separately. The current question appears once and saved AI
understanding retains its existing evidence/availability labels. Uncertain replies
retain the request identity and an explicit retry even for failed episodes.
Existing private references are collapsed; empty and legacy empty forms disappear,
while meaningful history remains readable. No private references enter research.

Core equality is checked after authorization, schema, replay and expected revision.
26 API regression tests passed for both products and the Legal storage alias,
including normalized no-op, initial empty, legacy empty, intentional clearing,
conflicts and exact replay. Required full-path Ruff and backlog gate passed.
