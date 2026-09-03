# Fedlex catalogue connector

HL-039 expands the direct ELI URL resolver into six bounded catalogue streams. The same normalized corpus and artifact pipeline used by other official sources remains the only persistence boundary.

## Streams

| Stream | Purpose | Cursor behavior |
| --- | --- | --- |
| `rss-de`, `rss-fr`, `rss-it` | Low-latency discovery from the three official recent-publication feeds | UTC publication watermark with a mandatory two-day overlap |
| `reconcile-cc` | Classified Compilation backfill and lifecycle reconciliation | Stable ELI keyset, 25 works per run by default |
| `reconcile-oc` | Official Compilation backfill and reconciliation | Stable ELI keyset, 25 works per run by default |
| `reconcile-fga` | Federal Gazette backfill and reconciliation | Stable ELI keyset, 25 works per run by default |

The RSS feeds are discovery accelerators rather than history. Each reconciliation call persists one bounded page, advances only after the page is safe, and resets to the beginning after a complete sweep. The later scheduler task HL-042 will decide cadence and fan-out.

## Identity and evidence

- The ELI work URI is the canonical key. SR/RS (`historicalLegalId`) is searchable metadata because it may be reused after a total revision.
- A work contains the titles and languages actually returned by JOLux. Each dated ELI expression is immutable and retains every advertised manifestation URI, format, and file reference.
- The connector downloads only the latest applicable HTML/display PDF for each language during catalogue ingestion. Future and older expressions remain saved as version metadata without being mistaken for the current text.
- Artifact fetch starts from the public ELI manifestation URI and follows the validated official redirect. The connector does not crawl blocked `/filestore/*` paths directly.
- The downloaded artifact is size-bounded, hashed, extracted, stored once, and linked to the exact expression and version date.
- A law already added through **Add law → Preview → Monitor** is matched to the catalogue by the same ELI work URI; its organization watch and legacy evidence remain intact.

## Dates, lifecycle, and relations

Publication, document, entry-in-force, no-longer-in-force, applicability, and version dates retain their official value, precision, URL, and `fedlex_jolux` provenance. The raw enforcement-status URI is retained rather than translated into an unsupported legal conclusion.

Confirmed relations come only from JOLux `basicAct`, `Citation`, and `LegalResourceImpact` records. The saved evidence includes direction, relation URI/class/type, information source, effective date, comment, source endpoint, and rule revision. A missing work, failed query, or empty unexpected response marks the stream degraded and never creates a repeal event.

Every newly discovered work and immutable document version creates an idempotent registry event. A lifecycle event is emitted only when an existing work's official status value actually changes. Incoming citations and impacts retain their official direction, so the amending or citing act remains the relation subject.

## Operation

Administrators can run one bounded page with:

```text
POST /api/connectors/fedlex/{stream}/sync
```

Use `GET /api/connectors/status` to inspect the cursor, safe checkpoint, schema/connector version, health, and last success. For a read-only live contract check that writes no corpus data:

```powershell
services/api/.venv/Scripts/python.exe scripts/check_fedlex_connector.py
```

The manual endpoint is an operational hook. Durable scheduled execution, per-watch fan-out, and cadence belong to HL-042.
