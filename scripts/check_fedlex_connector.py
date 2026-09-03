"""Run a bounded, read-only live contract smoke test against official Fedlex."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.config import Settings
from helvetic_lens.fedlex_connector import FedlexConnector


async def check() -> dict:
    settings = Settings(_env_file=ROOT / ".env")
    feed = FedlexConnector(settings, mode="rss", language="de")
    health = await feed.health()
    if health.status != "healthy":
        return {"status": health.status, "error": health.message, "stream": feed.stream}
    page = await feed.discover_since(None, {})
    reference = page.items[0]
    metadata = await feed.fetch_metadata(reference)
    expressions = await feed.list_expressions(metadata)
    relations = await feed.extract_relations(metadata)

    reconciliation = FedlexConnector(settings, mode="reconcile", collection="cc", page_size=1)
    reconciliation_health = await reconciliation.health()
    reconciliation_page = (
        await reconciliation.discover_since(None, {})
        if reconciliation_health.status == "healthy"
        else None
    )
    return {
        "status": "healthy"
        if reconciliation_health.status == "healthy" and reconciliation_page
        else "degraded",
        "feed": {
            "stream": feed.stream,
            "items": len(page.items),
            "sample_work": metadata.external_identity,
            "languages": sorted({item.language for item in expressions}),
            "versions": len({item.version_key for item in expressions}),
            "relations": len(relations),
        },
        "reconciliation": {
            "stream": reconciliation.stream,
            "status": reconciliation_health.status,
            "items": len(reconciliation_page.items) if reconciliation_page else 0,
            "next_cursor": reconciliation_page.next_cursor if reconciliation_page else None,
        },
    }


if __name__ == "__main__":
    result = asyncio.run(check())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "healthy" else 1)
