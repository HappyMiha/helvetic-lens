# Swiss Federal Criminal Court connector

HL-055 extends court coverage with the Swiss Federal Criminal Court because its decisions can directly affect criminal law, criminal procedure, mutual assistance, sanctions, financial crime, and compliance monitoring. The court says that it generally publishes its decisions and exposes newly added decisions on its official website. Helvetic Lens treats that website as the authority and retains the PDF link selected by the court.

## Source contract and honest coverage

- `latest` rereads at most the first 50 unique decisions in the official “Liste der neu aufgenommenen Entscheide” and persists them in pages of five. This overlap catches new and corrected listing entries while receipts and stable identities prevent duplicates.
- The work identity combines the document UUID in the court-linked document service with every docket displayed by the court. A listing correction changes the source revision; an unchanged overlap is idempotent.
- This is a latest-list connector, not a complete historical catalogue. A missing result means only that it was not observed in this source window. It never means that the court issued no decision.
- The official website links the PDFs through `bstger.weblaw.ch`. Helvetic Lens allows only the court website and that exact document-service host, stores the court page as discovery provenance, and does not use an independent aggregator as authority.
- The source publishes no crawl delay for these paths. Helvetic Lens applies a conservative one-second minimum between requests and runs the stream hourly with jitter.

## Shared corpus mapping

Each decision is stored as `court_decision` under authority `federal_criminal_court`, with its document UUID, one or more normalized dockets, official URL, federal court hierarchy, DE/FR/IT decision language, decision date, chamber when recognized, discovery timestamp, subject, artifact hash, and retrieval provenance.

The original PDF is the immutable evidence artifact and can be reopened from the stored version. Exact SR/RS references and article-plus-act citations from the first 40 pages become evidence-backed `cites` relations. This bounded citation scan is visible in metadata. A court decision is never represented as changing statutory wording.

## Failure boundary and verification

A missing latest-list heading, empty list, malformed document UUID, missing docket, non-PDF response, docket mismatch, unreadable PDF, or unrecognized decision date/language degrades the source without advancing its cursor. One bad item remains retryable at the page checkpoint.

Fixture tests cover incremental paging, overlap deduplication, listing revision detection, DE/FR metadata, cited norms, source drift, provenance, and reopening the original PDF. Run `scripts/check_federal_criminal_court_connector.py` for one bounded read-only live verification; it does not write to the corpus.
