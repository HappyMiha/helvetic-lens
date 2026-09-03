# Five-locale product verification

This record covers the executable part of the HL-057 acceptance gate on 3 September 2026. It does not replace native-language review. German, French, Italian, and especially Romansh still require a fluent reviewer before public beta.

## Environment

- Docker Compose development stack with PostgreSQL, Redis, API, workers, web application, and the local model manager.
- Local-first inference through `apertus-1.5b-q4km` (`Q4_K_M`) on the development GTX 1070.
- One active model slot and a 4,096-token local context profile.
- Desktop viewport and a 390 x 844 mobile viewport.
- Successful comparison: `a0daef60-68c3-4c28-b0e6-1dbcb5395eaf`.
- Identity-mismatch comparison: `cf027ea7-9ba2-4a10-952e-c1d82d7aab37`.

The identifiers above refer only to disposable local acceptance data. No credential or invitation token is part of this record.

## Browser path matrix

Each path was exercised in `de-CH`, `fr-CH`, `it-CH`, `rm-CH`, and `en-CH`.

| Path | What was verified | Result |
| --- | --- | --- |
| Login and registration | native-name language selector, translated headings and fields, immediate locale switch, correct page `lang` | passed in five locales |
| Registry | translated filters, date buckets and states; Unicode source content remains distinct from product language | passed in five locales |
| Successful comparison | translated semantic overview and Ask controls; exact official German evidence remains German and has source-language markup | passed in five locales |
| Citation navigation | saved AI answer exposes two accepted citations that open the exact persisted evidence | passed in five locales |
| Error comparison | identity mismatch is rendered from a stable reason code; no persisted English explanation leaks into localized UI | passed in five locales |
| Platform administrator | localized control-room heading, navigation and controls; installation actions are present | passed in five locales |
| Organization viewer | localized read-only notice; source mutations and platform controls are absent; direct `/admin` access returns the bounded authorization notice | passed in five locales |

At 390 px, the document width remained inside the viewport and essential controls were reachable. The mobile navigation is deliberately horizontally scrollable; off-screen navigation labels do not enlarge the page or clip their controls. Desktop layouts exposed the same actions without page-level horizontal overflow.

## Real local-Apertus samples

One unique change question per locale was sent through the running local model rather than a mocked provider. Every accepted sample used the complete persisted deterministic diff and one provider call.

| Output locale | Model result | Evidence | Provider calls |
| --- | --- | --- | ---: |
| `de-CH` | concise German before/after explanation | 2 validated citations | 1 |
| `fr-CH` | concise French before/after explanation | 2 validated citations | 1 |
| `it-CH` | concise Italian before/after explanation | 2 validated citations | 1 |
| `rm-CH` | concise Romansh before/after explanation | 2 validated citations | 1 |
| `en-CH` | concise English before/after explanation | 2 validated citations | 1 |

For these small-model answers, the server converted the model's validated citation selection into localized deterministic prose. Raw `old`/`new` labels and English internal coverage notes were not shown. The quoted law text remained in its official German language. Each stored result retained its requested `output_locale`, local model/runtime fingerprint, deterministic-diff context mode, and exact citations.

## Automated checks

The release check is:

```powershell
npm run check:i18n
npm run typecheck
npm run build
```

The catalogue check parses TSX and rejects missing and unused production keys, parameter/plural mismatches, unapproved hard-coded JSX/attribute/dialog/conditional text, and accidental cross-locale English inheritance. Its strengthened pass found and removed the remaining English `read` badge plus multiline local-model, credential, generation, connection-test, and reset guidance from Settings; the current 1,214 production keys and 1,094 literal calls pass. API regression tests cover locale-separated cache fingerprints, supported change-question recognition in all five languages, evidence validation, identity reason codes, and localized small-model answer rendering.

## Remaining release gate

- A different fluent reviewer for German, French, and Italian must approve the exact release catalogue and local-model wording.
- A native Romansh reviewer must approve the exact release catalogue and local-model wording.
- Reviewers must record concrete observations and every catalogue-key finding in an external copy of `demo/localization-review.template.json`.
- Findings must be corrected, tied to a resolution commit, and `python scripts/check_localization_review.py path/to/results.json --results` must pass from the clean reviewed commit before HL-057 is marked done.
