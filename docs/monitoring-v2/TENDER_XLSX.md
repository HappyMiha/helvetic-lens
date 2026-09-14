# XLSX tender conditions — 15 September 2026

Scope: the XLSX portion of MV2-044/045. This completes reading, comparing and
retrieving an already-permitted spreadsheet original in the private Tender
workflow. It does not establish live SIMAP attachment or Q&A access, or complete
B2. The nine Monitoring categories remain visible; C4 remains deferred.

## Result

The attachment parser recognizes the XLSX media type and validated octet-stream
OPC packages. It reads referenced worksheets in stable sheet/cell order, shared
and inline rich strings, finite numeric literals and booleans. Exact numeric
spelling is retained without float conversion, including integers above 2^53.
Each passage identifies the original package part, percent-encoded sheet name
and cell; rendered page numbers are not invented. The same original bytes and
SHA-256 remain available through the private original route.

Formula text has a separate locator. The parser neither calculates a formula
nor asserts that its cached value is current. Formulas, dates/error results,
number/date formatting, hidden content, external relationships, merged cells,
unsupported structures and Excel character escapes produce partial extraction.
The raw supported literals remain readable. Partial extraction cannot establish
unchanged or removed requirements. Complete means the supported literal cell
layer, not Excel rendering, calculation or legal completeness. Conservative
partial coverage can also occur for workbook themes and other unhandled parts.

Comparison preserves cell identity, type and exact whitespace. Moving identical
text to a different cell or renaming a sheet is material; changing an OPC member
filename, shared-string representation or XML/ZIP order alone is not. A 3-to-5
reference replacement uses the existing manifest revision and decision-review
workflow, without changing the public tender identity or rewriting its earlier
private decision.

The five-language reader explains literal values and formula limitations. Valid
complete/partial originals download as `.xlsx`; failed packages retain `.bin`.
Current owner, tenant, source, per-file, grant and retention checks apply before
text, original and comparison reads. No new credentials or source permissions
are introduced. Responses preserve attachment/no-store/nosniff/sandbox headers;
the browser never renders an original workbook inline.

## Parser boundaries

Only in-memory ZIP/XML parsing is used, with the shared bounded OPC reader:
256 members, 32 MiB declared expansion, 4 MiB per XML part, maximum 200:1
compression, 50,000 XML nodes per part / 100,000 cached nodes, depth 64 and
64 referenced sheets. Common 8 MiB original, 2,000-passage / 2 MiB text and
per-passage bounds still apply. No Office process, macro, formula evaluator,
external-link fetch or file extraction runs.

Malformed, duplicate/ambiguous, encrypted, macro-enabled, excessive or invalid
cell/reference packages fail with no authoritative partial output. Hashes of
the input are retained. Other Office formats, arbitrary archives, OCR and full
spreadsheet visual semantics are outside this increment.

## Primary format evidence

The public Microsoft documentation confirms [workbook/sheet relationships and
cell tables](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/structure-of-a-spreadsheetml-document),
[optional shared strings and rich-text runs](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/working-with-the-shared-string-table),
and the distinction between [formula text and cached results](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/working-with-formulas).
The Firecrawl Developer query returned the OfficeDev formula documentation;
Microsoft's primary pages were then read directly. No private data or account
credentials were sent to the documentation search.

## Verification

Synthetic actual ZIP/XML originals cover precise Unicode/whitespace, shared
strings, numerical precision, cells/sheet identity, formula cache exclusion,
partial coverage, malformed references, duplicate cells/ZIP parts, path escape,
macros, DTD/entities, encryption flags, CRC and extraction quotas. HTTP tests
exercise exact stored bytes, complete/partial/failed results, XLSX filenames,
source replacement comparison and current peer/revoked-grant denials. The
private revision test verifies reopening a prior decision and creating the
same-publication consented email intent; it sends no real email.

The integrated run passed 147 tests before the final extra end-to-end cases.
The isolated production frontend build passed. Final targeted verification and
browser results are recorded below when complete. Browser responses are
intercepted synthetic fixtures; actual byte-level checks run through the API.
No live source acquisition, production activation or human acceptance is claimed.

Final affected API/parser/store/observation run: **73 passed**, including actual
XLSX HTTP comparison with current access denial and material decision reopening.
The browser passed **36 full-document axe checkpoints** across five locales,
including spreadsheet guidance/cell locators, mobile overflow, both DOCX and
XLSX download filenames, denied-read recovery and injection rendering checks.
Other axe incomplete findings remain in the report; this is not an accessibility
certification. The 390px text view was inspected. Downloads stayed in the isolated
browser with download behavior denied, never the user's Downloads folder.

Local evidence: `.tmp/xlsx-integrated-2.log`, `.tmp/xlsx-final-1.log`,
`.tmp/xlsx-build-final.log`, `.tmp/xlsx-browser-final.log`,
`test-results/accessibility/tender-watch.json` and
`test-results/tender-xlsx-mobile.png`. Exact API Ruff, scoped Prettier,
browser script syntax and backlog integrity (1 test) passed before publication.
Production activation remains unverified at publication.

The authenticated production release page still showed `d961ebd54998` active
and `7fd0c80a2686` deploying at final review on 15 September. The running
automatic deployment was neither interrupted nor restarted.
