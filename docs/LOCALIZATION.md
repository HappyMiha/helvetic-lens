# Localization contract

Helvetic Lens supports `de-CH`, `fr-CH`, `it-CH`, `rm-CH`, and `en-CH`. Product language and source-document language are separate. A user may operate the product in Romansh while reviewing an official German passage; the passage remains German and its rendered block carries the source `lang` attribute.

## Resolution and persistence

The effective locale is selected in this order:

1. the authenticated user's saved preference;
2. the `helvetic_lens_locale` pre-login cookie;
3. the first supported browser or HTTP `Accept-Language` preference;
4. `HELVETIC_LENS_DEFAULT_LOCALE`, whose default is `en-CH`.

The language selector uses native names and writes the personal preference immediately. It never modifies organization-shared legal data. Invitation records retain the recipient locale; verification, recovery, and invitation mail use localized subjects, plain text, HTML, and locale-preserving links.

## Catalogue and contributor workflow

User-interface messages live in the namespaced catalogue in `apps/web/lib/i18n.tsx`. Stable API codes, enum values, IDs, URLs, model IDs, and evidence IDs are never translated at rest. FastAPI returns a stable `code` and typed `params`; the web boundary renders the matching localized message.

For a UI change:

1. add one semantic, namespaced English key instead of sentence fragments;
2. add German, French, Italian, and Romansh variants with the same named parameters;
3. use ICU-style `{count, plural, one {...} other {...}}` for counts;
4. run `npm run check:i18n`, type checking, and the production build;
5. inspect the longest translation at 390 px and desktop widths, using `pseudoTranslate` when a length stress case is useful;
6. have a fluent reviewer update the status table below.

The catalogue check rejects missing or unused literal keys and unapproved hard-coded English UI copy. The value audit evaluates the assembled catalogue, rejects unapproved English inheritance, and verifies that pseudo-locale expansion preserves named parameters. Runtime validation rejects missing locale entries and parameter/plural mismatches. Missing messages are a release error: production code does not silently fall back to English.

## Evidence and AI rules

- Official expressions model only languages actually published by the authority. Missing Romansh or English versions stay visibly absent.
- Official passages, quotes, citations, file names, and stated dates stay unchanged. A generated explanation or future generated translation is labelled as AI output and never stored as an official document version.
- Impact, Ask, and relation-impact requests carry `output_locale`. It participates in planning, cache and idempotency fingerprints, persisted results, and history labels. A cached answer in another language cannot be reused.
- A requested-language failure is retryable. It does not switch provider, cloud mode, or output language.
- Dates and times use `Intl` with `Europe/Zurich`; registry date buckets remain server-defined Swiss calendar periods. Search uses Unicode normalization and accent-insensitive matching over source metadata, never over an undisclosed translated corpus.

## Terminology

| Product concept | German | French | Italian | Romansh | English |
| --- | --- | --- | --- | --- | --- |
| saved evidence | gespeicherte Belege | preuves enregistrées | prove salvate | cumprovas memorisadas | saved evidence |
| monitored law | beobachteter Erlass | texte surveillé | legge monitorata | lescha survegliada | monitored law |
| impact inbox | Auswirkungs-Postfach | boîte des impacts | posta degli impatti | posta dals effects | impact inbox |
| source event | Quellenereignis | événement source | evento fonte | eveniment da funtauna | source event |
| review suggestion | Prüfvorschlag | suggestion de vérification | suggerimento di verifica | proposta da controlla | review suggestion |

Use language that distinguishes a possible impact from an official legal relation. Avoid translating *Apertus*, *Fedlex*, identifiers, or quoted official titles.

## Review status

| Locale | Catalogue status | Human language review |
| --- | --- | --- |
| `de-CH` | complete production catalogue; automated inheritance check passes | pending final public-beta review |
| `fr-CH` | complete production catalogue; automated inheritance check passes | pending final public-beta review |
| `it-CH` | complete production catalogue; automated inheritance check passes | pending final public-beta review |
| `rm-CH` | complete production catalogue; automated inheritance check passes | pending native review |
| `en-CH` | source catalogue | reviewed in automated product flows |

The executable five-locale browser, authorization, responsive-layout, error, citation, and real local-Apertus checks are recorded in [the verification report](LOCALIZATION_VERIFICATION.md). HL-057 remains in progress until fluent reviewers approve German, French, Italian, and Romansh and any findings are corrected. This document records current capability without presenting automated review as native-language approval.
