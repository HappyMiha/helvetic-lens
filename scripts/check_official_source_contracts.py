"""Run bounded, read-only live contract probes for the first official connectors."""

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.config import Settings
from helvetic_lens.official_source_contracts import (
    OFFICIAL_SOURCE_CONTRACTS,
    probe_source_contract,
)


async def main() -> int:
    settings = Settings(_env_file=None, allow_private_sources=False)
    results = []
    failed = False
    for contract in OFFICIAL_SOURCE_CONTRACTS:
        result = await probe_source_contract(settings, contract)
        results.append(
            {
                "connector": contract.manifest.name,
                "url": contract.smoke_url,
                **asdict(result),
            }
        )
        failed = failed or result.status != "healthy"
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
