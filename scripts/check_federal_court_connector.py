"""Run one bounded, read-only live Federal Supreme Court connector check."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.config import Settings
from helvetic_lens.extraction import extract
from helvetic_lens.federal_court_connector import FederalCourtConnector


async def main() -> int:
    settings = Settings(_env_file=None, allow_private_sources=False)
    connector = FederalCourtConnector(settings, mode="latest", item_page_size=1)
    health = await connector.health()
    if health.status != "healthy":
        print(json.dumps({"status": health.status, "message": health.message}, indent=2))
        return 1
    page = await connector.discover_since(None, {})
    reference = page.items[0]
    metadata = await connector.fetch_metadata(reference)
    expression = (await connector.list_expressions(metadata))[0]
    artifact = await connector.fetch_official_artifact(expression)
    relations = await connector.extract_relations(metadata)
    extracted = extract(
        artifact.body,
        artifact.content_type,
        artifact.filename,
        "official_connector",
    )
    print(
        json.dumps(
            {
                "status": health.status,
                "newest_insertion_date": health.source_contract["observed"][
                    "newest_insertion_date"
                ],
                "crawl_delay_seconds": connector.manifest.minimum_interval_seconds,
                "aza_identity": metadata.external_identity,
                "docket": metadata.metadata["docket"],
                "decision_date": metadata.metadata["decision_date"],
                "insertion_date": metadata.metadata["insertion_date"],
                "language": expression.language,
                "chamber": metadata.metadata["chamber"],
                "artifact_sha256": metadata.metadata["artifact_sha256"],
                "artifact_characters": len(extracted.text),
                "relations": len(relations),
                "next_cursor": page.next_cursor,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
