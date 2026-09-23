# Influence Graph

The `/influence` workspace lets a researcher assemble an evidence dossier, inspect
relationships as a graph or list, and preserve corrections and editorial decisions.
It extends the existing Helvetic Lens application and deployment pipeline.

## Using the module

1. Open **Influence Graph** from the desktop navigation or mobile overflow menu.
   Select the public reference dossier or an accessible workspace dossier.
2. Choose graph/list, an entity and an evidence perspective. Select a numbered
   connection or list row to read its sources, counter-statements and limits.
   Graph zoom and scrolling support larger dossiers. Parallel claims remain
   separate connections. The evidence list contains the same filtered records.
3. A workspace administrator can choose **New dossier** or **Copy to workspace**.
   Add entities, then sources, then relationships. Give each claim its own source
   locator, summary and limits. Source publication dates may be unknown; check
   dates must be explicit. Optional exact quotes require a matching retained extract.
4. Supply a reason and save. Each save creates a new revision; it never overwrites
   prior evidence. If another save wins first, the request fails with a conflict
   and the draft remains available. Preserve your changes, cancel and load the
   latest version before reconciling. A retry of the same request does not append
   a duplicate revision.
5. Review the current revision with **Reviewed** or **Needs revision**, plus a note.
   A review records an editorial decision, not automatic verification of claims.
   A later revision starts without reviews. History reopens exact earlier JSON
   and the decisions attached to it. Archive/restore also records a revision.
6. Export downloads the selected dossier, revision hash and its review records as
   JSON. It includes retained extracts; handle it as workspace research content.

Viewers have read/export access within their workspace. Administrators author and
review. Private dossiers require authentication even in anonymous development mode.
They are never published into the bundled reference. The interface uses the five
existing application locales; dossier text retains its selected authoring language
(English, German, French, Italian, Romansh or Ukrainian). F1 section help is English,
consistent with the existing application help system.

## Evidence rules

- Every relationship joins two different saved entities and cites at least one
  saved source with a locator and summary. It also states its limits.
- `documented` requires a primary source and no unresolved counter-statement.
  `disputed` requires a counter-statement. Reporting remains attributed; potential
  policy effects cannot be marked as documented outcomes.
- **Confirmed money flows** includes only paid, documented dividends with primary
  evidence, amount, currency and a completed reporting period. It does not traverse
  ownership or family links to infer payments. Proposed distributions are excluded.
- Source URLs must use HTTPS without credentials. The API does not fetch those URLs
  or send dossier text to an AI provider. Retained extracts are text supplied by the
  editor, not an authenticated capture of the live page. Editors remain responsible
  for the accuracy and permitted use of source material.
- SHA-256 binds the exact retained dossier JSON, including extracts. It does not
  certify the source, author, live URL or truth of a claim. Immutability is enforced
  through the API's append-only workflow; the hash is not an external timestamp.

## Public reference source register

Checked on **22 September 2026**, with 12 entities, 12 relationships and six sources.
This is a dated research snapshot, not a continuously updated investigation.

| Source | Date | Bounded use |
|---|---|---|
| [EMS Finance Report 2025](https://www.ems-group.com/fileadmin/user_upload/EMS-Group/news/2026/2026-03-24_Finanzbericht/EMS_Group_Finance_Report_2025_684152.pdf) | 24 March 2026 | Note 19: disclosed holdings; Note 32: group interests in two Russian subsidiaries; cash-flow statement: aggregate dividends paid in 2025 |
| [Magdalena Martullo-Blocher corporate biography](https://www.ems-group.com/en/investors/corporate-governance/board-of-directors/magdalena-martullo-blocher/) | Undated | Published family relationship, management role and disclosed holding-company interests |
| [Initiative committee](https://neutralitaet-ja.ch/abstimmungskomitee/) | Undated | Christoph Blocher's listed campaign role |
| [FDFA neutrality explanation](https://www.eda.admin.ch/en/neutrality) | 1 September 2026 | Initiative's proposed sanctions rule; described as a proposal at the snapshot date |
| [Republik investigation](https://www.republik.ch/2026/09/04/die-geschaefte-der-blochers-in-russland) | 4 September 2026 | Attributed reporting about EFTEC and named Russian vehicle manufacturers; underlying records were not retained here |
| [EMS response to Blick Online](https://www.ems-group.com/de/medien/finanz-medienmitteilungen/ems-gruppe/detail/dementi-der-ems-chemie-zu-falscher-berichterstattung-von-blick-online-am-17926/) | 17 September 2026 | Company's denial and stated limits on Russian business; explicitly a reply to Blick, not falsely described as a direct reply to Republik |

The CHF 403,461,000 dividend edge is the group's aggregate 2025 payment to
shareholders. It is not attributed to one family member, Russian income or military
customers. Consolidated 100% subsidiary interests do not assert an immediate legal
parent chain. Possible economic effects of the initiative remain unestablished.
No personal Russian military payment, donor-register trail or individual dividend
receipt has been established by this reference dataset. No source archive is claimed.

## Architecture and API

`apps/web/components/influence-page.tsx` owns workspace selection and authenticated
requests. `influence-editor.tsx` handles drafts; `influence-reader.tsx` handles the
graph/list and evidence panel. `lib/influence-graph.ts` owns types and filters;
`lib/influence-dossier.ts` is the public seed, and `lib/influence-copy.ts` owns labels.
Private state is keyed to user, organization and management permission. It is held
in memory, with cancellation guards for ordinary navigation and stale list results.

`services/api/helvetic_lens/influence_api.py` registers through the existing main
application. It uses the normal auth/CSRF middleware, fresh membership checks,
administrator transaction locks and organization filters. All module responses,
including authorization/validation failures in the main app, receive `no-store`.

| Method and endpoint | Contract |
|---|---|
| `GET /api/influence/dossiers` | Workspace list; `archived`, UUID `after_id`, bounded `limit` |
| `POST /api/influence/dossiers` | Create; `document`, `note`, UUID `requestId`, `expectedRevision: 0` |
| `GET /api/influence/dossiers/{id}` | Current document or historical `revision` |
| `PATCH /api/influence/dossiers/{id}` | Append revision using `expectedRevision`; stable request key for retries |
| `POST /api/influence/dossiers/{id}/reviews` | Current revision decision, note and stable request key |
| `POST /api/influence/dossiers/{id}/archive` | Archive/restore, expected revision, reason and stable request key |
| `GET /api/influence/dossiers/{id}/history` | Descending revisions; `before_revision` and bounded `limit` |

Storage limits: 100 dossiers per workspace, 500 revisions per dossier, 50 reviews
per revision, 100 entities/sources and 250 edges per document, 600 KB canonical JSON.
The server validates evidence references and chronology. Request payloads cannot
choose organization or actor identity. Edits use compare-and-swap and a transaction;
retries must match the original payload. Old review decisions remain attached to
their exact revision. Account erasure sets actor foreign keys to null; organization
deletion cascades its dossiers, revisions and reviews.

Migration `d1c495bef124` adds only `influence_dossiers`, `influence_revisions` and
`influence_reviews` after `e1c495bef124`. Existing domain tables and evidence-review
variants are unchanged. Normal deployment startup applies it. Rolling back application
code can leave these unused additive tables; do not downgrade a populated database
as a routine rollback, because the down migration drops the new research data.

## Verification and release

The local reference/filter/localization tests are integrated into `npm run typecheck`
and `npm run build` through `npm run check:influence`. The isolated Python suite uses
the actual router, SQLAlchemy models and full Alembic migration chain on disposable
SQLite, with explicit synthetic trusted identities. It covers revision/review
history, retries, stale edits, cross-tenant denial, viewer/revoked-member denial,
actor erasure and cascade deletion. It does not simulate production auth as passing.

Normal verification commands in a working project environment:

```text
npm run build
uv run --project services/api ruff check services/api deploy/release_manager.py
uv run --project services/api pytest services/api/tests/influence services/api/tests/test_influence_graph.py services/api/tests/test_auth.py services/api/tests/test_migration_foreign_keys.py services/api/tests/test_account_erasure_store.py -q
uv run --project services/api pytest services/api/tests/test_monitoring_progress.py::test_actual_backlog_has_complete_unique_sections_and_preserves_customs_deferral -q
```

Session evidence and unresolved release checks are recorded in
[VERIFICATION.md](VERIFICATION.md). Release preparation on 22 September 2026
integrated upstream main through `bb233c9` and set the verified GitHub origin to
`https://github.com/HappyMiha/helvetic-lens.git`, resolving the earlier restricted
session's Git/network and dependency blockers. All 44 selected API tests now pass,
including the full-application auth/CSRF/restart cases, using the project runtime.
The new migration follows upstream `e1c495bef124` so Alembic retains one head.
The production build and its 357 frontend tests pass, including TypeScript and the
five-language checks. PostgreSQL verification, browser/visual acceptance and
deployment activation remain open; local checks do not establish those outcomes.

The only release target is `helveticlens.ch` on HappySnowman. This module does not
create another deployment. [MV2-064 / HL-053](../BACKLOG_MONITORING_V2.md#mv2-064)
continues to require its separate legal relationship-graph usefulness experiment.

## Document review briefs (23 September 2026)

In **Edit dossier → Dossier**, choose a monitored document and add findings,
discussion notes or tasks. Notes retain contributor names/roles, an explicit
fictional-contributor flag and references to the dossier's sources. Tasks also
have a status and an internal target date. Each save creates a dossier revision;
a task date is not a statutory deadline and a fictional name is not a user account.
These editorial records never populate AI analyses or authorize operational actions.

The document page displays active linked briefs; its graph button opens the exact
private dossier at `/influence?dossier=<id>`. The graph opens first, with the brief
available below it. Legal connections participate in the policy filter. Original
source texts retain their language while the controls support all five locales.

`GET /api/influence/dossiers/by-law/{id}` checks fresh membership and the current
organization's document watch. It returns at most ten latest active linked briefs,
without retained source extracts. Create/edit also validate document visibility;
private law identifiers cannot be linked across organizations. Existing dossier
revisions store the optional fields, requiring no new database migration.

Verification: 91 targeted API tests, exact repository Ruff gate, root frontend
checks and production build. Local authenticated browser checks covered exact
links, the 15-note editor, task status/save and law/graph navigation. Real Fedlex
historical HTML exposed a Virtuoso SQ200 constant-sort error; the resolver now
sorts only variable dimensions and retains deterministic artifact ordering.
Native fetches of the 2021 and 2023 OR editions pass, alongside a regression test.
The production dossier's source facts are distinct from fictional company and
colleague content; production activation and populated-data checks are recorded
separately in the delivery record.
