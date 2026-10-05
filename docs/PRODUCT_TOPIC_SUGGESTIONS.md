# Durable topic suggestions

An explicit Suggest topics request is queued on the existing `ai_interactive`
lane. Background research can continue; the browser receives a request receipt
without waiting for inference. The author can reopen the draft and recover the
same validated cards. Suggestions do not select or activate monitoring topics.

`POST /monitoring-profiles/{id}/suggestions` accepts a stable UUID request key,
expected draft revision, feedback and locale. `GET` on the same path reads the
latest request for the currently authorized requester, or `request: null`. Requests
are bound to their original input and current access; changed or activated drafts
make old output superseded. Completed results retain the existing TopicSuggestions
shape. The existing synchronous `/suggest` endpoint remains compatible.

Linked dossiers retain their existing setup permissions for editors and owners.
Only standalone native drafts are creator-only. Suggestion results are private
to the requester, even when several authorized editors share the same dossier.

Existing PostgreSQL jobs and the transactional outbox own execution, private
result storage, retries and lease recovery. Generic job readers do not expose
these author-private inputs or results. Busy admission waits in the queue and
is distinguished from a model or platform failure. No new infrastructure, table,
source acquisition or provider call is introduced by polling.

Local verification: 19 new HTTP/worker cases passed for queued admission,
idempotency and concurrent-intent coalescing, exact saved cards, busy recovery,
manual selection, changed inputs/access, collaborator permissions, private
results and cancellation/replacement/expiry, including same-worker lease reclaim.
Twelve affected existing suggestion
and domain-profile cases also passed. Three broader federation fixtures still
expect an older two-catalogue list; their unchanged production paths return the
current registered catalogues. They are separate from this implementation.
The exact backlog integrity gate, `ruff check services/api deploy/release_manager.py`
and `git diff --check` passed. Publication and live model acceptance remain
unverified.
