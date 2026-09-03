# Regulatory corpus contract

HL-036 introduces the common persistence boundary used by future Fedlex, Parliament, court, and notice connectors. It does not replace the current `Law`, `Version`, `Observation`, or `Comparison` APIs. Those records remain the evidence and monitoring compatibility layer while connectors move to the normalized corpus incrementally.

## Identity hierarchy

`RegulatoryWork` represents one authority-level subject: act, ordinance, parliamentary business, initiative, bill, court decision, or official notice. A mutable URL is never its only identity. `RegulatoryIdentifier` stores authority-scoped ELI URIs, SR/RS numbers, parliamentary business IDs, court dockets, stable official URLs, and provisional legacy identities. The merge boundary normalizes identifiers, prefers the strongest available scheme for a canonical key, and refuses to merge a descriptor whose identifiers already point to different works.

`RegulatoryExpression` stores an available source-language expression. Adding French or Italian text for a known ELI creates another expression under the same work. `RegulatoryDocumentVersion` is an immutable descriptor keyed within an expression and may point to the existing saved `Version` and artifact. Connector retries with the same keys return the existing rows.

Official works have no owner and are shared. A direct-URL document without confirmed official identity receives an organization-owned provisional work and a `LegacyDocumentMapping`. The session boundary exposes only public works or provisional works owned by the active organization. A later official connector may point the mapping at a confirmed public work without rewriting old evidence, version IDs, or comparisons.

## Dates, events, and relations

`RegulatoryDate` stores source-stated `published_at`, `version_date`, `effective_from`, `effective_to`, and `decision_date` facts separately from Helvetic Lens `detected_at` and artifact `fetched_at`. Values stay as source strings with `instant`, `day`, `month`, `year`, or `unknown` precision, provenance, source URL, and optional evidence. The application must not turn a fetch timestamp into an official date.

`RegulatoryEvent` accepts only `created`, `new_version`, `amended`, `repealed`, `replaced`, `status_changed`, `decided`, and `notice_published`. Creating an event requires explicit source evidence and a provenance method. A missing catalogue result, disappearance, timeout, or fetch failure is therefore a connector error and creates no lifecycle event.

`RegulatoryRelation` stores `amends`, `repeals`, `replaces`, `implements`, `cites`, `interprets`, and `potentially_impacts`. Every row carries evidence, a fingerprint, provenance method, optional source version and model/rule revision, and a `confirmed`, `proposed`, or `rejected` state. A review decision creates a new row that supersedes the earlier relation; it does not overwrite the evidence history.

## Connector write boundary

Connectors call `RegulatoryCorpus.merge_document`, `record_event`, and `record_relation` inside the same database transaction as cursor advancement. The database constraints and deterministic dedupe keys make replay safe. Read-only inspection is available through `GET /api/corpus/works` and `GET /api/corpus/works/{id}`. Catalogue pagination, scheduling, and source-specific parsing belong to HL-038 and the individual connector tasks.
