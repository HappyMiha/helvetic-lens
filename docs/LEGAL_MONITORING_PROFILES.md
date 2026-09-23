# Legal monitoring profiles: reference analysis and implementation

Requested on 23 September 2026. Scope: bring the uploaded RegWatch project's
five-step user journey into the existing Helvetic Lens production application.
H26-07 and the legal-first-value contribution to MV2-002 track this delivery.

## Reference audit

The archive contains 76 files (371,852 uncompressed bytes): a TanStack Start /
React application, a component library and Lovable planning metadata. The actual
route implements five steps: Context, Topics, Sources, Delivery and Activate.
The later planning note describes four steps but has not been applied to the
code. The user's explicit five-step request and implemented route are the basis.

The valuable design is progressive disclosure: one decision per screen, visible
progress, editable topic cards, sources grouped by legal role, a delivery preview,
and a final confirmation. Client/firm context gives the choices a concrete purpose.
The result should remain understandable without configuring a crawler or an API.

The reference is a presentation prototype, not a connected monitoring service:

- `generate()` waits 1.1 seconds and returns the same medical topics regardless
  of keywords or feedback. Legal references are fixed, unverified strings.
- The 13 initial source names have empty URLs and no collector/status checks.
  A custom URL becomes a local Requested badge; nothing fetches or stores it.
- The example judgment `1C_xxx/2026`, date and legal conclusion are fictional.
  They cannot become production alert evidence.
- Activation only sets a React boolean. Account fields are not validated or
  submitted. No profile, subscription, authentication or delivery is created.
- Reload loses every choice. New-profile reset retains previous topics, sources,
  delivery and account data. Topic titles are unstable React keys during editing.
- Dashboard profiles and activity timestamps are fixed examples. Export timestamps
  change while rendering, and disabled/requested provenance is lost in the JSON.
- Email/instant alert choices have no scheduler. The API-handoff claim has no
  corresponding API. There are no behavior, privacy or activation tests.

## Production design

Keep Next.js, FastAPI, PostgreSQL, existing authenticated organizations, the
official source catalogue, immutable topic revisions, matching jobs and personal
digest delivery. Port the journey and interaction patterns; do not import a
second application, fixed legal claims, fake activity or the archive's runtime.

1. **Context:** client or own organization, profile name and sector. Persist a
   private draft so Back/Next, reload and later continuation retain input.
2. **Topics:** user intent, genuine configured-model suggestions, editable stable
   topic cards and manual creation. Failure stays visible; no canned AI fallback.
   Reference notes remain unverified user/proposal notes, not legal evidence.
3. **Sources:** choose real catalogue packs, inspect coverage and collection gaps.
   Additional URLs are saved requests with explicit inactive collection status.
   A requested jurisdiction/source does not establish available coverage.
4. **Delivery:** preview actual saved matching events with evidence links or an
   honest empty state. In-app monitoring always works independently of email.
   Optional daily/weekly email uses the existing personal organization digest;
   disclose its scope and preserve current delivery unless explicitly changed.
5. **Activate:** review/edit each section, then atomically save real topics,
   selected source subscriptions and optional delivery settings. Retried activation
   must reuse the same result. Show only persisted profiles and their real state.

Creation and activation require an organization administrator. Drafts belong to
their author; activated profiles are visible to the organization. Existing source
rights, model quality, membership, CSRF and email verification gates stay intact.
The new entry is available to every organization alongside existing navigation.

## Acceptance criteria

- Complete five-step flow, keyboard/mobile usability and all five UI languages.
- Durable draft/reload, Back/Next preservation, editing and clean new-profile state.
- Genuine topic suggestion from supplied context/feedback; manual path on failure.
- Actual source coverage and saved-event preview; no fabricated laws or alerts.
- Atomic activation; duplicate/retry protection and stale-revision errors.
- Real profile list and native topic history, evidence, pause/resume and matching.
- Delivery choices connect to the existing personal digest without silently
  subscribing colleagues or claiming unsupported instant email/Slack/Teams.
- Tenant isolation, owner-private drafts, viewer denial, CSRF, membership refresh,
  migration/restart persistence, failure rollback and credential-free exports.
- Required lint/tests/build/browser checks, immediate main publication, verified
  automatic release and read-only production checks. No test client data seeded
  into production merely to demonstrate this flow.

## Implemented architecture

`/monitoring-profiles` lists real saved profiles; `/new` starts a clean draft and
`/[id]` resumes the saved step or opens the activated profile. Desktop/mobile
navigation, Today and Topics expose the entry. Product copy covers English,
German, French, Italian and Romansh, with contextual English help as elsewhere.

Migration `f2c495bef124` adds organization-scoped profiles with author ownership,
creation keys, revisions, timestamps, configuration, server-issued proposal
provenance and native topic links. Saving Back/Continue or Save draft is durable;
unsaved changes are explicitly indicated. Context, refinement feedback, selected
topic cards, source requests and delivery choices survive saving and reload.

`legal_profiles.py` composes existing topic/source/digest operations. The short
organization lock serializes profile mutations; activation commits topics,
immutable topic revisions, subscriptions, jobs/outbox and optional personal
digest changes together. The existing helper defaults still commit for their
original callers. Retries reuse activation; stale saves and late model responses
cannot replace a newer revision. AI metadata is issued by the server, never
accepted from a submitted card. Manual topic entry works independently of AI.

Catalogue filters determine exact matching jurisdictions, including `CH-BS`
for Basel-Stadt. Requested external jurisdictions are not added to monitoring.
Each preview uses the native matcher against at most 500 organization-visible
saved events and displays at most ten examples per topic, with evidence links,
match reasons, sample bounds and operational source coverage. Custom source
requests remain explicitly inactive and are retained in profile export.

Activated topics expose their real state, saved matches and native history.
Pause/resume changes non-archived linked topics together. The activation choices
remain a historical setup record; later expert edits live in topic revisions.
Shared source subscriptions are not disabled by pausing one profile.

Daily/weekly email requires verified email and SMTP. The default keeps current
delivery. Explicit consent changes only the current user's organization digest,
retaining its existing filters and clock. Activation does not immediately send
email. Draft erasure follows the author, while activated shared profiles retain
organization history and detach the erased actor.

## Verification, 23 September 2026

- Exact API lint passed. The final affected API/regression run passed all 34
  cases; three affected checks also passed after normalizing SQLite timestamps
  to explicit UTC. The complete production frontend build passed.
- API behavior: durable save/reload, idempotent activation, topic history and
  pause/resume, rollback after a second-topic failure, actual saved evidence
  preview, empty/invalid source rejection, requested-source provenance, real
  model-input/feedback flow and manual recovery, server-issued AI provenance,
  consent and email transport gates, preservation of existing digest filters,
  author-private drafts, cross-organization isolation, CSRF and refreshed viewer
  denial, URL/duplicate-card validation, late model-result conflicts, physical
  account erasure, migration/reconnection persistence and cantonal matching.
- Regression: native topics, source packs, account erasure and the required
  Monitoring backlog uniqueness/customs-deferral check.
- Frontend: the repository build runs i18n/value, navigation, resource-cache,
  report, contextual-guide and Influence Graph checks, then Next/TypeScript.
- Browser: an isolated local authenticated workspace completed all five steps
  using a controlled model fixture. Reload resumed Topics; accepted suggestions
  stayed editable; an additional source stayed Requested; preview displayed
  the actual zero saved events and source readiness; activation created one
  native topic; pause/resume changed that topic; a new profile reset all fields.
  Desktop and 390 px mobile views were inspected; no horizontal document
  overflow occurred. Production acceptance will be read-only, without seeding
  test client records or changing an existing organization's monitoring.

## Boundaries

This delivers the uploaded legal workflow, not universal jurisdiction coverage
or the broader nine-direction MV2 onboarding acceptance. Profiles currently
support six topic cards and ten additional source requests. The latter record
intent and still need a separately configured, approved source. Topic suggestion
quality depends on the organization's configured provider; proposals are human
reviewed search interests, not law analysis or legal evidence. There is no
instant-email, Slack or Teams claim. Email remains the existing personal
organization digest rather than independent per-client mailings.

Status: VERIFYING — implementation and local acceptance complete; automatic
production release and read-only verification pending publication.
