# Fedlex article ranges and the OR / VSOP demonstration

## Scope recorded before implementation — 23 September 2026

MV2-068 scoped legacy-import extension, with MV2-020/023 evidence and question
integration. Implement one continuous German Fedlex range in Sources → Add a
law: structural preview, immutable selected evidence, persisted scope, safe
rescans and questions on the first saved version through the existing cited Ask
pipeline. The feature is available to every organization under existing roles;
Selected scopes, snapshots and AI records retain organization ownership, while
whole-document public-corpus reuse remains unchanged. Parent MV2 acceptance remains open.

Dependencies: existing Fedlex JOLux resolver, bounded fetcher, saved versions,
document watches, comparison/Ask validation, migrations and five-language UI.
The live OR artifact retrieved on 23 September has official applicability date
2026-01-01, 2,684,235 bytes and structural `main#maintext article#art_322_d`
elements. Letter suffixes use underscores in IDs and separate inline elements
in headings. Section headings are ancestors, not article body text.

Acceptance: import complete Art. 319–323b including 322d; preview and saved
scope survive reload; identical/outside-range changes stay unchanged; missing
or ambiguous articles preserve the last good snapshot; distinct ranges and
languages have distinct identity/history/cache; a first-version question uses
real Ask with exact retained citations or an honest unsupported result; whole
document imports, tenant access and required checks remain intact. Live-source
checks and controlled synthetic changes must be reported separately.

The user subsequently authorized production publication and availability in all
organizations. No organization profile changes are part of this demonstration.

## Verification and demonstration

Implemented in the existing Sources → Add a law dialog, with “Selected articles”,
first/last article inputs and a mandatory UI preview. The preview exposes the full
selected text, 16 structural headings, scope and character count. Changing the
selection clears the preview; a changed text hash requires a new preview at save.
Document detail, saved evidence and the first-version Ask page display the scope
and the official date separately from the first retrieval timestamp. UI strings
and range errors cover de/fr/it/rm/en. The first-version page reuses durable Ask
jobs, cache, history, role checks and exact citation validation. Its internal
snapshot context is excluded from the comparison/change timeline.

Selected ranges are organization-owned records, available to every organization
without a feature flag. Existing administrators manage imports/scans/questions;
existing readers can inspect retained evidence. A different range creates a
separate document; identities include range and source language. Whole-document
public-corpus reuse is unchanged. No demonstration data or fictional company
profile is seeded into production.

### Executed checks (23 September 2026)

- Exact required Ruff gate: `ruff check services/api deploy/release_manager.py`.
- Root `npm run build`, including i18n, shell/navigation, resource flows, reports,
  help, influence and the Next production build/type check: passed.
- Standard `npm run test:release`: 753 passed (95 smoke, 658 functional).
- Affected extraction/Ask/registry/evidence/history/migration/backlog integration
  selection: 130 passed (129 integration, one backlog smoke). The new article
  suite contributes 23 cases. Five invalid-range cases were rerun after mapping
  request validation to the localized range error; all passed.
- Existing whole-document extraction/language/workflow checks: 56 passed.
- SQLite migration upgrade/downgrade retains foreign keys and existing evidence
  revision triggers. The downgrade uses native DROP COLUMN; table replacement
  had removed an existing trigger and was corrected before release.

The affected integration selection is reproducible with:

```sh
PYTHONPATH=. uv run --project services/api python -m pytest \
  services/api/tests/test_article_selection.py \
  services/api/tests/test_analysis.py \
  services/api/tests/test_registry_timeline_projections.py \
  services/api/tests/test_registry_monitored_pages.py \
  services/api/tests/test_evidence_pages.py \
  services/api/tests/test_document_history_pages.py \
  services/api/tests/test_migration_foreign_keys.py \
  services/api/tests/test_extraction_transition.py \
  services/api/tests/test_monitoring_progress.py::test_actual_backlog_has_complete_unique_sections_and_preserves_customs_deferral -q
```

### Live source and browser evidence

An isolated development database was used with the real Fedlex resolver and the
existing real local `apertus-8b-q4km` runtime. No mock AI was used for these browser
checks. Sources → preview → save imported the complete 319–323b scope without
the MVP text-limit error: **16 articles, 10,846 characters, official date
2026-01-01**. Both paragraphs of Art. 322d are retained. Reload preserved scope,
date, text and evidence. A subsequent real Fedlex scan returned **Unchanged** and
retained exactly one version. The scope panel was inspected in all five UI
languages. The final document page was visually checked in the browser.

The official artifact checked was:

<https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/27/317_321_377/20260101/de/html/fedlex-data-admin-ch-eli-cc-27-317_321_377-20260101-de-html-12.html>

The primary question below made one real model call and returned validated
citations to **319, 322 and 322d** (three supplied passages, 1,539 characters).
Its Art. 322d citation opened the exact retained passage. The official link was
opened and the `#art_322_d` anchor and both paragraphs verified on Fedlex.
The second question returned an explicit unsupported answer: the selected
evidence does not settle the question and no contract/case law was reviewed.
The third returned selected excerpts only, not a legal evaluation of forfeiture.
These outcomes are evidence of a working cited question path, not acceptance of
the model's legal reasoning quality. The present local capability permits
**selected evidence**, not a generated VSOP legal opinion.

Browser testing caught and corrected an official-date label that called it
user-supplied, multi-article retrieval that initially lost 322/322d, and repeated
history quotes that exhausted the local 4K context. Snapshot requests now send
at most two bounded conversational excerpts; full prior answers/citations remain
saved. Model token measurement, capability gates and citation checks remain in
force. Failed attempts remain visible in the isolated test history.

### Controlled fixture evidence

`services/api/tests/fixtures/fedlex-or-20260101-range.html` retains the official
article structure/text and adjacent Art. 318/324 for deterministic tests.
Edits inside/outside the selection, missing/duplicated/reordered articles,
empty bodies, fetch errors, changed previews and invalid citations are **synthetic
test cases**, not amendments to the live OR. Tests show inside changes detected,
outside-only changes unchanged, and failures preserving the last successful
snapshot. Separate authenticated organizations cannot read each other's selected
range documents, snapshots or question contexts. Different ranges have separate
histories and Ask cache keys. Unknown official dates remain unknown.

### Demo in 3–5 minutes

1. Sign in as an organization administrator. Open Sources → Add a law. Enter
   `https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de` and a display name.
2. Choose Selected articles, First article `319`, Last article `323b`. Preview.
   Expand Articles found: verify 16 entries including 322d and the scope
   `Art. 319–323b OR, DE`. Save.
3. Open saved articles. Show the retained text, official date and first-saved
   date. Return and select Ask about saved text; no older edition is required.
4. Paste the fictional case and question 1 below into the question itself.
   Show the actual response-mode/coverage labels. Ask question 2 as a follow-up;
   do not describe an unsupported response as a legal conclusion.
5. Open citation 322d, then its Official article link. The anchor is
   `#art_322_d` on the resolved official HTML artifact.
6. Return to document detail and Run scan now with the previous live version.
   If Fedlex is unchanged, show Unchanged and the same retained version. Do not
   stage a fictional live legislative amendment.

Fictional case (do not write it into a real organization profile):

```text
Demo-Fall: Eine Schweizer AG plant einen rein virtuellen Mitarbeiterbeteiligungsplan (VSOP). Mitarbeitende erhalten keine Aktien, sondern eine mögliche Geldzahlung bei einem Exit. Der Plan enthält Vesting- und Leaver-Klauseln. Der konkrete Vertrag liegt noch nicht vor.
```

Question 1:

```text
Welche Bedeutung haben Art. 319, 322 und 322d OR für die arbeitsrechtliche Einordnung dieses VSOP? Belege deine gesetzlichen Aussagen mit den gespeicherten Artikeln. Unterscheide Gesetzestext und deine Einordnung.
```

Question 2:

```text
Welche Vertragsangaben fehlen, um zwischen Lohn und Gratifikation zu unterscheiden? Kennzeichne, welche Fragen anhand der geladenen Gesetzesartikel allein nicht beantwortet werden können.
```

Question 3 (optional; inspect the coverage/limitations):

```text
Welche Fragen entstehen, wenn bereits gevestete Ansprüche bei Kündigung verfallen sollen? Nenne die relevanten gespeicherten Gesetzesstellen und kennzeichne ausdrücklich, wo zusätzliche Rechtsprechung und der konkrete Vertrag benötigt werden.
```

### Limits and release boundary

- Native German Fedlex consolidated HTML only; one continuous range of positive
  numeric articles with at most one letter suffix. No PDF fragments, grouped
  repeal IDs, `bis` numbering, other languages or arbitrary websites.
- Strict structural boundaries, full article bodies and up to three ancestor
  headings. Paragraphs/lists and local editorial notes are retained. Editorial
  changes still produce an exact text change. Comparison classification can mark
  paired footnote renumbering and inline HTML layout as formatting when verified
  against the retained original. Exact evidence and footnote wording remain
  intact; changed legal numbers or wording remain substantive. A missing or
  corrupt original stops regeneration of that comparison.
- Download timeout/size limits remain; the parser independently caps input at
  8 MiB and selections at 500 articles. The existing 1.2M-character/6,000-passage
  analyzed-text limits apply after selection. This is not full-OR ingestion.
- A changed article sequence on rescan requires review and preserves the good
  snapshot. It does not infer repeal. A different desired scope must be imported
  as a new monitored document. Historical imports must be official German HTML
  of the same legal work.
- AI uses only the selected, token-bounded evidence. Narrow contexts can omit
  articles; explicit article numbers improve targeting. Existing local capability
  approval limits explanations. The full law, case law, contract, tax treatment
  and legal validity were not reviewed.
- Release is authorized for all organizations through normal automatic main-site
  deployment. This file records pre-publication acceptance; pushed code must be
  distinguished from subsequent public readiness/deployment verification.
  Broader MV2-068 and independent legal-quality acceptance remain open.

### Production review walkthrough

The English Legal Hackathon dossier is linked directly from the monitored OR
document. Open its **Review brief**, inspect **Findings**, **Discussion** and
**Tasks**, then follow **Open Influence Graph** to the exact same dossier.
Select an edge to inspect its cited original, date, explanation and limitations.
The graph connects the pre-2013 wording, accounting amendment and legislative
history with related provisions, decisions and dated professional commentary.
Company-specific effects are conditional; fictional contributors are identified.
The organization retains its original profile and existing AI results.

The three saved official HTML editions are 2021-01-01, 2023-01-01 and 2026-01-01.
Use their comparisons to show editorial differences without suggesting a new
employment-law amendment. The substantive historical change is documented with
the official 2012 consolidated PDF and the amending act effective in 2013. These
PDF sources belong to the review/graph evidence, not the selected-HTML parser.
