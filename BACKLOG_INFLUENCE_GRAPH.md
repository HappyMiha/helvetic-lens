# Influence Graph

User direction, 22 September 2026: **Helvetic Lens → Influence Graph**, followed
by an explicit request for the complete module and a push to main for deployment.
[Usage, architecture and verification](docs/INFLUENCE_GRAPH.md).

| Item | Status | Acceptance |
|---|---|---|
| IG-001 — Evidence dossier explorer | VERIFYING | Graph and equivalent list; dated sources and counter-statements; strict money filter; five interface languages; keyboard/mobile support; production build |
| IG-002 — Workspace authoring and editorial review | VERIFYING | Tenant-scoped authoring; permitted source extracts; immutable revisions and revision-specific reviews; stale-write protection; retries; archive/restore; JSON export; authorization and deployment checks |
| IG-003 — Automated acquisition and entity resolution | PLANNED | Future approved connectors, duplicate review and source rights; the current module supports manual source entry without fetching URLs |
| IG-004 — Document review brief and linked graph | IN PROGRESS | Organization-scoped document links; editable cited findings, discussions and assigned tasks; immutable revisions; explicit fictional contributors; exact graph links; production content verification |

## IG-004 — Document review brief and linked graph

User direction, 23 September 2026: populate Legal Hackathon in production in
English with real OR sources/history, company implications, fictional colleagues,
discussion and tasks, accessible from the monitored law and Influence Graph.
Reuse private dossier revisions, authorization and citation validation. Add an
optional monitored-document link and bounded editorial notes; never fabricate an
AI result or grant model capabilities. Every organization can use the feature;
the authored Legal Hackathon content remains private to that organization.
Source readiness: official Fedlex OR HTML editions from 2021 onward, the 2011
accounting amendment and official explanatory history, and BGer 4A_388/2025.
Earlier consolidated editions need separate official PDF evidence; unchanged
selected provisions must not be presented as a new amendment.
Acceptance: fresh membership and document-visibility checks; viewer reads/admin
writes; missing citation rejection; archived dossier exclusion; linked law and
exact dossier navigation; notes remain separate from AI and retain their actual
save times; English content with five-language controls; tested release and
verified target-organization data. No external messages or fictional accounts.

## IG-001 — Evidence dossier explorer

The /influence route uses the existing shell, navigation and locale selection.
Its public reference dossier concerns Christoph Blocher, EMS and the Neutrality
Initiative, with six sources checked on 22 September 2026. Graph and list share
entity, documented-relationship, money and policy filters. Each relationship
retains direction, type, status, effective date, source locators, counter-statements
and limits. Source text stays in its authored language; the interface supports
English, German, French, Italian and Romansh.

Confirmed money requires a documented, paid dividend with amount, currency, period
and primary evidence. Ownership and possible policy effects never infer payments.
Disputed claims present report and response together. Group dividends are not
allocated to a person or to Russian income. Consolidated interests are not an
immediate legal-parent chain. Missing evidence does not establish absence.

Dependencies: existing web application and auth shell. Source readiness: the EMS
finance report and corporate biography, initiative committee list, FDFA explanation,
Republik report and EMS response. Publication dates or undated markers are explicit.
The public reference retains metadata and paraphrases. No archived original,
individual payment receipt, bank record or verified donor register is claimed.

Implemented locally: graph/list, inspectable evidence, separate parallel
connections, scroll/zoom, filters, empty states, status text, responsive layout,
five-language labels and English section help. Automated filters and a Next
production build have passed. Browser/visual acceptance, independent editorial
review and deployed-route verification remain open; IG-001 is not DONE.

## IG-002 — Workspace authoring and editorial review

Administrators create a blank dossier or copy the public reference, manage entities,
sources and claims, retain permitted extracts, save revisions, record review
decisions and archive/restore. Viewers read/export accessible workspace dossiers
and history. Private dossiers never become part of the bundled public reference.

Implemented locally: three additive database tables; organization scope and fresh
membership checks; administrator transaction locks for writes; compare-and-swap
revision checks; idempotent create/save/review/archive; bounded lists and history;
exact quote validation against retained extracts; primary evidence requirements
and dispute rules; revision-specific decisions and SHA-256 of retained JSON.
Editing does not inherit old reviews. Earlier evidence remains readable.
User erasure detaches actor references; organization deletion cascades its dossiers.
Private browser state is in memory, keyed by account/workspace/management permission,
with unsaved-edit navigation guards and draft retention on request failure.

Dependencies: existing auth/CSRF middleware, membership locks, SQLAlchemy and normal
Alembic startup migrations. No new runtime packages, AI provider, collector,
external credential or deployment service is required.

The contract, SQLite router/migration and full-application auth/CSRF/restart
tests pass with synchronized project dependencies. The release selection passes
44 tests, including authentication, account erasure and the required backlog gate.
PostgreSQL verification and production activation remain open.

## IG-003 — Automated acquisition

Future scope. Source URLs are citations, not fetch targets. Automated ingestion
requires approved connectors, source rights, retained artifacts, stable identities
and duplicate review. Manual authoring and review are implemented independently.

## Release boundary

Release preparation on 22 September 2026 safely integrated the 32 upstream
commits through main bb233c9. The origin now points to the verified repository,
https://github.com/HappyMiha/helvetic-lens.git. The earlier Git/network and Python
dependency blockers are resolved; main-only hooks remain enabled.

The new, unpublished migration now follows upstream e1c495bef124, preserving one
Alembic head. The exact Ruff gate, 44 selected API tests, 357 frontend checks,
five-language audit, TypeScript, production build and affected-file formatting
pass. Code publication and deployment activation are separate from these local
checks; verify activation only on helveticlens.ch on HappySnowman.

MV2-064 / HL-053 remains DEFERRED. This work does not change graph_review_v1 or
satisfy the legal relation-list-versus-graph usefulness experiment.

### IG-004 implementation evidence — 23 September 2026

The document link, bounded cited notes, fictional-contributor labels, internal
workflow dates, five-language editor/reader, legal-connection type and exact graph
navigation are implemented. Private rows reuse the existing revision tables;
there is no schema migration or model-output substitution. Ninety-one targeted
API tests passed, including fresh visibility, revoked membership, viewer access,
missing citations, archive exclusion and historical note retention. Root frontend
checks/build and the exact Ruff gate pass. Local authenticated browser validation
covers the actual English dossier, task editing and revision saves. Official
historical HTML fetching now avoids Fedlex Virtuoso's constant-sort SQ200 error.
Release activation and the Legal Hackathon population remain to be verified.
