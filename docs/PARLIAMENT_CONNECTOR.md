# Swiss Parliament connector

HL-040 imports parliamentary business from the official legacy web service through the shared connector runner. It keeps proposals visibly distinct from enacted law and stores the authority's stable identifiers, language records, lifecycle state, source links, and retrieval time.

## Discovery streams

| Stream | Purpose | Cursor behavior |
| --- | --- | --- |
| `catalogue` | Complete lightweight bootstrap and periodic full reconciliation | Walks every official 50-row, ID-ordered page in bounded 10-item slices, then begins a new reconciliation cycle |
| `recent` | Fast revisit of newly allocated/current-year IDs | Cycles over the last four official pages in bounded slices |
| `active` | Frequent revisit of already known non-final business | Keyset-pages the saved non-final affair IDs and resets only after the active set is covered |

The source-contract spike found no reliable global `updated` ordering or update-only filter on the affairs catalogue. The list is ordered by ID, and old affairs can receive a new `updated` value. The three streams therefore complement each other; the scheduler in HL-042 will set their cadence.

## Identity, language, and versions

- The numeric affair ID is the stable primary authority identifier; the displayed short ID remains a searchable secondary identifier.
- The adapter requests DE, FR, IT, and EN, then trusts the response's actual `language` value. An EN request that falls back to FR does not create a fictional English expression.
- Titles and source text are retained per available language. HTML fragments inside official JSON are converted to readable extracted passages while the exact source URL, substantive JSON projection, source revision, hash, and retrieval time remain attached to the immutable version.
- A record version key hashes substantive fields such as titles, texts, drafts, references, and document links. A state-only API update changes work metadata and emits `status_changed` without manufacturing a new text version.
- One unique official linked document per available URL is downloaded through the common size, redirect, hash, extraction, and immutable-storage boundary. All advertised official artifact metadata remains on the work even when it is not eagerly downloaded.

## Metadata and relations

The normalized work retains affair type, stable state ID and localized state names, deposit/publication date, authors, committees, legislative period/session, descriptors, related affairs, votes endpoint, official artifacts, source revision, and retrieval timestamp. The required attribution is stored with every connector receipt:

> Parlamentsdienste der Bundesversammlung, Bern

Exact ELI and SR/RS mentions become evidence-backed `cites` relations. The API's explicit `relatedAffairs` entries become proposed `potentially_impacts` candidates because the field confirms a relationship but does not state its legal effect. Bare article and Federal Gazette references remain deterministic candidates in metadata until a target work can be resolved. Title similarity alone creates no relation.

## Operation

Administrators can run one bounded slice with:

```text
POST /api/connectors/parliament/{catalogue|recent|active}/sync
```

`GET /api/connectors/status` exposes health, source/schema version, cursor, partial checkpoint, and last success. The read-only live smoke writes no corpus data and downloads no linked document:

```powershell
services/api/.venv/Scripts/python.exe scripts/check_parliament_connector.py
```

The adapter is intentionally isolated behind `parliament-webservice-v2`, because Parliament has announced a future replacement while keeping the current service available until further notice.
