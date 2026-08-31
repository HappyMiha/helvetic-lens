# Source compatibility

These are configurable examples, not a built-in allowlist. Measurements were taken through the real native extraction API on 31 August 2026; websites may change. Counts describe extraction, not legal completeness.

| Source | Observed output | Limitations |
| --- | --- | --- |
| [FINMA circulars listing](https://www.finma.ch/en/documentation/circulars/) | HTML; “FINMA’s supervisory practice”; English; 2,042 characters, 41 passages | Static introduction plus listing/navigation fragments. The circular list uses JavaScript, so native discovery is partial. Do not treat the introduction as a particular circular. |
| [FDPIC data-protection FAQ](https://www.edoeb.admin.ch/en/faq-data-protection) | HTML; “Frequently asked questions on data protection concerns”; English; 87,127 characters, 176 passages | Main FAQ text is extractable. It is guidance, not the full text of an act. Long-document AI coverage is limited and disclosed. |
| [FDPIC 30th report, 2022–2023](https://www.edoeb.admin.ch/dam/en/sd-web/SdN6dbrPrj9f/30_Report_2022-2023_EN.pdf) | Text PDF; filename used as title; English; 108 pages, 208,487 characters, 1,622 passages | Annual report for parser/page-reference verification, not a previous version of a law. PDF blocks may include running headers, footnotes, and layout artifacts. |

The [FDPIC legal-basis page](https://www.edoeb.admin.ch/en/legal-basis-data-protection) links to statutes and reports. Links to [Fedlex's FADP landing page](https://www.fedlex.admin.ch/eli/cc/2022/491/en) lead to a JavaScript application. Use a direct downloadable PDF for native monitoring if the landing page cannot yield the legal text.

## Historical inputs

[policy-previous.txt](../demo/policy-previous.txt) and [policy-current.html](../demo/policy-current.html) were authored for this project. They are two versions of the same fictional policy, including an exact **30 → 60** change. Mark both the current source and historical import as synthetic in the UI. A stated date remains user-supplied.

Do not attach an annual report or synthetic policy to an unrelated real act as if it were that act's earlier version. For actual history, obtain an older copy of the same document and retain its provenance.

## Boundaries

- Native HTML selects main/article content when possible and removes common navigation, scripts, forms, headers, and footers. It does not execute JavaScript. Unusual structure and template fragments can require a better direct URL.
- Discovery stays within the selected host and path, without recursive crawling or off-host expansion. Candidate extraction happens when selected for preview.
- PyMuPDF extracts text and page numbers. Image-only and password-protected PDFs are rejected; no OCR is included.
- Login-gated sources are unsupported.
- Firecrawl is an explicit optional provider, requesting a fresh scrape with maxAge=0. No silent fallback or bundled credit is provided, and no real Firecrawl result has been validated for this build.
- Fetch/import timestamps are not official effective dates. Snapshots retain their first provenance; subsequent observations separately record how content was obtained.
