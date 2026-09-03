"""Read-only, one-item live verification for HL-050 connectors."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.broad_official_connector import (
    FederalNewsConnector,
    FinmaNewsConnector,
)
from helvetic_lens.config import Settings
from helvetic_lens.fedlex_connector import FedlexConsultationConnector


async def verify(connector):
    health = await connector.health()
    if health.status != "healthy":
        return {
            "connector": connector.manifest.name,
            "stream": connector.stream,
            "status": health.status,
            "message": health.message,
        }
    page = await connector.discover_since(None, {})
    result = {
        "connector": connector.manifest.name,
        "stream": connector.stream,
        "status": "healthy",
        "discovered": len(page.items),
        "complete": page.complete,
        "cursor": page.next_cursor,
    }
    if page.items:
        metadata = await connector.fetch_metadata(page.items[0])
        expressions = await connector.list_expressions(metadata)
        artifact = await connector.fetch_official_artifact(expressions[0]) if expressions else None
        result.update(
            {
                "sample_identity": metadata.external_identity,
                "kind": metadata.kind,
                "lifecycle_status": metadata.lifecycle_status,
                "expressions": len(expressions),
                "artifact_bytes": len(artifact.body) if artifact else 0,
                "relations": len(await connector.extract_relations(metadata)),
            }
        )
    return result


async def main():
    settings = Settings(_env_file=None)
    connectors = (
        FederalNewsConnector(settings, page_size=1),
        FinmaNewsConnector(settings),
        FedlexConsultationConnector(settings, page_size=1),
    )
    results = [await verify(connector) for connector in connectors]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(item["status"] != "healthy" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
