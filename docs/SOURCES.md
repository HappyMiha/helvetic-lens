# Source compatibility

These are configurable examples, not a built-in allowlist. Measurements were taken through the real native extraction API on 31 August 2026; websites may change. Counts describe extraction, not legal completeness.

| Source | Observed output | Limitations |
| --- | --- | --- |
| [FINMA circulars listing](https://www.finma.ch/en/documentation/circulars/) | HTML; “FINMA’s supervisory practice”; English; 2,042 characters, 41 passages | Static introduction plus listing/navigation fragments. The circular list uses JavaScript, so native discovery is partial. Do not treat the introduction as a particular circular. |
| [FDPIC data-protection FAQ](https://www.edoeb.admin.ch/en/faq-data-protection) | HTML; “Frequently asked questions on data protection concerns”; English; 87,127 characters, 176 passages | Main FAQ text is extractable. It is guidance, not the full text of an act. Long-document AI coverage is limited and disclosed. |
| [FDPIC 30th report, 2022–2023](https://www.edoeb.admin.ch/dam/en/sd-web/SdN6dbrPrj9f/30_Report_2022-2023_EN.pdf) | Text PDF; filename used as title; English; 108 pages, 208,487 characters, 1,622 passages | Annual report for parser/page-reference verification, not a previous version of a law. PDF blocks may include running headers, footnotes, and layout artifacts. |
| [Fedlex FADP ELI](https://www.fedlex.admin.ch/eli/cc/2022/491/en) | Native ELI resolution; current applicable English HTML; “Federal Act on Data Protection”; 39,543 characters, 331 passages | Resolved through official SPARQL metadata to the 7 July 2025 expression during the 1 September 2026 check. Counts may change with a new applicable consolidation. The stable ELI URL remains tracked. |
| [Fedlex FADP, 1 September 2023](https://fedlex.data.admin.ch/eli/cc/2022/491/20230901/en/html) | Explicit English HTML expression; 38,851 characters, 328 passages | The version and format are pinned by the ELI URL and are not advanced to the current consolidation. Useful as authentic historical input for the same act. |
| [Fedlex FADP revision message](https://www.fedlex.admin.ch/eli/fga/2017/2057/fr) | Native ELI PDF fallback; French; 238 pages, 694,033 characters, 2,435 passages | This is a Federal Gazette message, not the consolidated FADP. PDF layout and metadata can contain encoding or block-order noise. |
| [Fedlex NFA message](https://fedlex.data.admin.ch/eli/fga/2002/316) | Language-neutral Federal Gazette ELI URL; deterministic German PDF/A fallback; “BBl 2002 2291”; 269 pages, 674,707 characters, 3,042 passages | Verifies that a bare ELI work URL resolves through official metadata instead of saving the Fedlex JavaScript shell. The explicit `/fr`, `/it`, or other supported language suffix remains available when that publication exists. |
| [Swiss Parliament affairs](https://ws-old.parlament.ch/affairs) | Official 50-row catalogue pages, stable and short IDs, DE/FR/IT records, lifecycle state, source text, committees/sessions, exact references, and linked official documents | The list is ID-ordered rather than update-ordered; complete reconciliation and known-active revisits are required. An English request may return a French fallback, which is stored as French rather than inventing English coverage. Required attribution and retrieval date accompany reused data. |
| [Swiss Federal Supreme Court new decisions](https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index&search=false) | Official insertion-date index and authoritative decision HTML with Aza/docket identity, chamber, actual language, separate decision/insertion dates, artifact hash, and exact legal references | The published crawl delay is two seconds. The sitemap declared in `robots.txt` covers website pages rather than decision records, so bounded date-index reconciliation supplies current/previous-year coverage. No source PDF is claimed when the official free representation is HTML. |
| [Swiss Federal Criminal Court new decisions](https://www.bstger.ch/de/home/index) | Official latest-decision list with stable document UUID/docket identity and court-linked PDF evidence | Covers only the decisions visible in the current latest list. It is not a complete historical catalogue, and absence never establishes that no decision exists. The connector keeps a 50-item overlap and a one-second request floor. |

The [FDPIC legal-basis page](https://www.edoeb.admin.ch/en/legal-basis-data-protection) links to statutes and reports. Supported Fedlex ELI law URLs may point at the JavaScript application: the native fetcher detects those URLs and resolves the official HTML/PDF file through Fedlex metadata. Fedlex search pages and unrelated JavaScript routes are not resolved.

## Historical inputs

[policy-previous.txt](../demo/policy-previous.txt) and [policy-current.html](../demo/policy-current.html) were authored for this project. They are two versions of the same fictional policy, including an exact **30 → 60** change. Mark both the current source and historical import as synthetic in the UI. A stated date remains user-supplied.

Do not attach an annual report or synthetic policy to an unrelated real act as if it were that act's earlier version. For actual history, obtain an older copy of the same document and retain its provenance.

## Boundaries

- Native HTML selects main/article content when possible and removes common navigation, scripts, forms, headers, and footers. It does not execute JavaScript. Supported Fedlex ELI law URLs use the fixed official SPARQL endpoint and validated official publication-store URLs; this is a narrow resolver, not a general browser. Unusual structure and template fragments can require a better direct URL.
- Discovery inspects at most 50 direct candidates within the selected host/path, prioritising PDF/TXT links and excluding common navigation. It follows no links inside those candidates. Native redirects outside the boundary are rejected; returned rendered-provider URLs are also checked. Previews and individual errors are persisted, with a 120-second inspection budget and explicit coverage counts.
- pdfminer.six extracts ordered text blocks and physical page numbers through the shared `pdf_reader` module. Court metadata reads the opening 40 pages; persisted document evidence reads the complete file within the 1,000-page / text-size limits. Image-only and encrypted PDFs are rejected; no OCR is included.
- Login-gated sources are unsupported.
- Firecrawl is an explicit optional provider, requesting a fresh scrape with maxAge=0. No silent fallback or bundled credit is provided, and no real Firecrawl result has been validated for this build.
- Fetch/import timestamps are not official effective dates. Snapshots retain their first provenance; subsequent observations separately record how content was obtained.

## PDF extractor change, 4 September 2026

New PDF extractions record `<provider>-pdfminer-v1`; HTML and plain-text extraction
retain their existing version. Original PDF bytes remain available and repaired
line-break hyphenation keeps the raw block text for inspection. The shared reader
uses pdfminer.six directly under MIT; ReportLab is a development-only fixture
generator. No PDF rendering engine or AI call is required.

Eight locally saved PDFs (2 to 176 pages) were re-extracted successfully on the
development host, taking approximately 0.08 to 12.01 seconds each. A fresh native
Fedlex fetch of the NFA message (`eli/fga/2002/316`) also passed: 269 pages,
677,990 characters, 5,689 passages, and 17.14 seconds for extraction (download time
excluded). This checks real-file readability, not independently verified legal completeness. The older
measurements in the table above are historical and should not be treated as exact
counts for the new parser. Regression tests cover column order, soft wraps,
Unicode metadata/text, blank-page citation offsets, encryption, malformed files,
page limits, and full extraction beyond the court metadata excerpt.

Existing test snapshots are not rewritten or deleted automatically. For a clean
demo, import both comparison versions with the new extractor; differences caused
only by switching parsers are not evidence of a legislative amendment. Rebuild
the API and worker images before using the new extractor; old images still carry
their historical dependencies and licenses.
