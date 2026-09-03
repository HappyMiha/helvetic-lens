# Official notices

HL-043 adds contextual publications without presenting them as legal instruments or court holdings.

## Supported source

The Swiss Parliament `notices` stream reads the official SharePoint/OData `Pages` list behind `parlament.ch/press-releases`. It advances on the official `(Modified, Id)` watermark, stores each source revision once, and retains German, French, Italian, English, and Romansh expressions when the authority exposes them. Each expression keeps the official URL and an immutable extracted body; provenance also records the hash and content type of the downloaded official HTML page.

Exact ELI URLs, SR/RS identifiers, and Curia Vista `AffairId` values found in the official body become deterministic `cites` relations. Unstructured names are retained as evidence but are not promoted to relations by this connector.

Registry rows are marked `official_notice` and explicitly describe the item as contextual authority information. A single `notice_published` event represents all language expressions of one source revision, preventing multilingual duplicates in the event feed.

## Deliberate source boundaries

- Fedlex has stable feeds for the Classified Compilation, Official Compilation, and Federal Gazette. Those publications already enter through the Fedlex legal connector. Treating the same Federal Gazette manifestation as a separate news notice would duplicate evidence and blur its legal status, so HL-043 adds no second Fedlex notice stream.
- The Federal Supreme Court decision connector remains healthy for its supported official decision index. Its public press area does not currently provide a documented machine feed with the same reliable incremental identity and change watermark. HL-043 therefore does not add an unbounded page crawl.
- Federal Council, department, regulator, consultation, and general government news belong to HL-050. This task does not crawl `news.admin.ch`.

If an authority later publishes a stable feed, add it as another bounded stream under the shared connector contract rather than widening an existing legal-record crawler.
