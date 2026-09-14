# Questions about native Monitoring evidence

Status: implemented release candidate; final verification and publication below.
Scope: MV2-023, with MV2-020 reader integration.

Whole feature: from an individual record in each of the nine active directions,
open an evidence question panel, inspect the selected source version and retrieve
matching exact extracts with citations. It works without a model. This replaces
neither the original source reader nor the existing navigation help in Marvin.
Natural-language configuration drafts and independently evaluated generative
answers remain required broader MV2-023 work; this feature does not close it.

Dependencies are the existing authenticated native evidence readers, native
version/configuration checks, source display permissions, locale catalogue and
private frontend lifecycle. No new source credentials or permission grants are
needed. Display permission does not imply permission to send evidence to a model;
this implementation makes no inference or external source requests.

Acceptance before publishing this whole feature:

1. All nine record readers provide an explicit evidence-question action. The
   panel identifies the selected record and exact version, with original-reader
   citations and clear current/historical/unavailable state.
2. Each request reuses the native reader's identity, membership, ownership or
   explicit workspace scope, source permission, configuration and retention checks.
   A request cannot supply source prose, arbitrary URLs or another user's context.
3. Exact source extracts are searched deterministically. No generated medical,
   infringement, safety or deadline conclusions are presented. Unsupported
   questions receive an explicit no-supported-extract result. Official instructions
   remain unchanged. A cited extract is evidence, never an instruction to the app.
4. Responses carry a binding to the selected native evidence/configuration and
   extractor/locale revision. Changed evidence invalidates an earlier selection;
   source withdrawal prevents redisplaying cached answers. No answer is persisted
   as a current conclusion or implicitly reused across scopes.
5. No monitor mutation, activation, source query, bid, mail, review decision or
   model invocation occurs. Questions and extracts are not written to public logs.
6. Five-language desktop/mobile UI supports loading, empty, unavailable, changed,
   retry and exact-citation navigation. Closing, changing context, losing access
   or leaving the page clears extracts and rejects late responses.
7. Verify real native readers for all nine directions, cross-user/workspace denial,
   source revocation, stale bindings, prompt injection, no mutation/model calls,
   required API lint, web build and built-browser accessibility/workflow checks.
   Exact release activation and independent human acceptance remain separate.

## Implemented contract

The existing Pollen, River, Air, Hazard, Commute, Road, Tender, IP and Auction
readers now expose the same expandable evidence panel. Personal feeds/selected
records and the three business item readers use their existing identities and
native versions. Source permission gates are independent of section visibility;
no new flag hides the panel. Page-guide controls explain the action in all nine
sections. The guide remains English, while the panel is available in five locales.

`POST /api/monitoring-centre/evidence/ask` accepts only typed record identifiers,
an optional native history sequence, locale, bounded question and selected binding.
Source text, arbitrary URLs, commands and extra context are rejected. Reading
normalized source fields through existing native readers does not grant artifact
export, model processing or private document access. No source collection, model,
work action or outgoing message occurs. Questions/answers are not persisted.

This is explicitly word matching over saved source fields. It is a manual,
extractive fallback, not generative question answering. Results preserve exact
scalar text, original field references and available station/period/unit/currency
context. A keyword match is not presented as an interpreted conclusion. Empty or
punctuation-only searches cannot invent an answer. Bounds are 2,000 question
characters, 256 KB of selected display data, 1,000 extracts, 16,000 characters per
extract and twelve displayed matches. Oversized evidence fails explicitly and
the native original reader remains available; no silent truncated warning is
called a complete answer.

Bindings cover the full native read, selected record/history, extractor revision
and locale. Changed source/profile/reader state rejects a saved binding. Citation
links use a separate authenticated, no-store reference read with the same binding;
they show existing normalized display fields and cannot redirect silently to new
evidence. Raw artifacts and new export permissions are not exposed. Native source
withdrawal or lost private/workspace access is checked on every question and
reference request. Earlier displayed material is explicitly saved evidence,
with access-check time; it is not a claim of continuously verified live status.

The client clears extracts before a request, on failure, closure, page hiding,
identity/role/workspace/locale changes and changed component context. Aborted late
responses cannot refill another context. Reloading evidence clears the old query;
searched text is displayed alongside its own result. Original field text is
escaped by React. Returning to the original record performs no review or mutation.

## Local verification

The earlier combined affected run passed 37 tests, including notification and
business-item HTTP regressions. After adding unit context and a public Tender
withdrawal case, the focused nine-domain/API suite passed 25 tests. The suite uses
real synthetic ingestion/native readers in all nine directions, exact field
extraction, private/shared viewer isolation, material changes, permissions,
boundaries, source revocation, no SQL work mutations and actual model call counts.
These fixtures grant no production source coverage or human acceptance.

The isolated root `evidence-ask` build passed. Browser acceptance passed 81
full-document axe checkpoints on the shared panel in three native business
readers, all five locales and desktop/mobile widths, covering no matches,
changed/wrong context, denied access, historical selection, viewer reads,
close and a held response after pagehide. Mobile screenshots were inspected;
text wraps without horizontal overflow. Other axe incomplete checks and independent
screen-reader/language/user review remain open. Final authenticated citation-link
checks and the backlog invariant passed together (26 tests); the final compiled
browser run passed all 81 checkpoints, including exact local citation identities
and bindings. Desktop and mobile screenshots were inspected. After the SQLite
migration repair, all 25 feature tests passed again. A further seven checks proved
the six personal readers retain their bindings across later requests and the
backlog still preserves its complete task index and customs deferral.

Reproduce with the three `test_monitoring_evidence_*.py` files under
`services/api/tests`, the exact API Ruff gate and the root build. For the built
browser suite, first run `scripts/prepare_business_item_browser.py` to generate
synthetic native contracts, set `HELVETIC_LENS_CHECK_BUILD=evidence-ask`, build,
then run `npm run check:monitoring-evidence:browser`. Browser requests are fixtures;
the nine-domain API tests independently exercise the real readers.

MV2-023 remains IN PROGRESS: natural-language drafts, generative/cached conclusions,
model/prompt evaluation, source/live acceptance and independent human review are
not completed by this extractive feature. C4 and grants remain deferred.
