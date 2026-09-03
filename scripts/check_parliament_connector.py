"""Run a bounded, read-only Swiss Parliament connector contract check."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.config import Settings
from helvetic_lens.connectors import DiscoveryReference
from helvetic_lens.parliament_connector import ParliamentConnector


async def main() -> int:
    connector = ParliamentConnector(
        Settings(_env_file=None, allow_private_sources=False),
        mode="recent",
        item_page_size=1,
        recent_window_pages=1,
    )
    health = await connector.health()
    if health.status != "healthy":
        print(json.dumps({"status": health.status, "message": health.message}, indent=2))
        return 1
    page = await connector.discover_since(None, {})
    reference = page.items[0]
    metadata = await connector.fetch_metadata(reference)
    expressions = await connector.list_expressions(metadata)
    relations = await connector.extract_relations(metadata)
    document_records = await connector._load_details("20250069")
    document_primary = next(iter(document_records.values()))
    document_reference = DiscoveryReference(
        "20250069",
        str(document_primary["payload"]["updated"]),
        (
            "https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft"
            "?AffairId=20250069"
        ),
        document_primary["artifact"].url,
    )
    document_metadata = await connector.fetch_metadata(document_reference)
    document_expressions = await connector.list_expressions(document_metadata)
    print(
        json.dumps(
            {
                "status": health.status,
                "observed": health.source_contract.get("observed"),
                "sample_affair": reference.external_identity,
                "source_revision": reference.source_revision,
                "title": metadata.title,
                "kind": metadata.kind,
                "lifecycle_status": metadata.lifecycle_status,
                "languages": metadata.metadata.get("available_languages"),
                "expressions": len(expressions),
                "official_artifacts": sum(
                    len(items)
                    for items in metadata.metadata.get("official_artifacts", {}).values()
                ),
                "relations": len(relations),
                "next_cursor": page.next_cursor,
                "document_sample": {
                    "affair": document_reference.external_identity,
                    "languages": document_metadata.metadata.get("available_languages"),
                    "official_artifacts": sum(
                        len(items)
                        for items in document_metadata.metadata.get("official_artifacts", {}).values()
                    ),
                    "downloadable_expressions": sum(
                        item.metadata.get("record_kind") == "official_linked_document"
                        for item in document_expressions
                    ),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
