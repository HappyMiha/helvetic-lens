"""Run one bounded, read-only live Federal Criminal Court connector check."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.config import Settings
from helvetic_lens.extraction import extract
from helvetic_lens.federal_criminal_court_connector import FederalCriminalCourtConnector


async def main() -> int:
    settings = Settings(_env_file=None, allow_private_sources=False)
    connector = FederalCriminalCourtConnector(settings, item_page_size=1)
    health = await connector.health()
    if health.status != "healthy":
        print(json.dumps({"status": health.status, "message": health.message}, indent=2))
        return 1
    page = await connector.discover_since(None, {})
    reference = page.items[0]
    metadata = await connector.fetch_metadata(reference)
    expression = (await connector.list_expressions(metadata))[0]
    artifact = await connector.fetch_official_artifact(expression)
    extracted = extract(artifact.body, artifact.content_type, artifact.filename, "official_connector")
    relations = await connector.extract_relations(metadata)
    print(
        json.dumps(
            {
                "status": health.status,
                "latest_decisions": health.source_contract["observed"]["latest_decisions"],
                "document_id": metadata.external_identity,
                "dockets": metadata.metadata["dockets"],
                "decision_date": metadata.metadata["decision_date"],
                "language": expression.language,
                "chamber": metadata.metadata["chamber"],
                "artifact_sha256": metadata.metadata["artifact_sha256"],
                "artifact_characters": len(extracted.text),
                "citation_candidates": len(relations),
                "coverage": connector.manifest.source_contract["coverage"],
                "next_cursor": page.next_cursor,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
