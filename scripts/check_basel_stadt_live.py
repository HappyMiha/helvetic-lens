"""Bounded live acceptance in a disposable local database; no AI or production access.

Run with PYTHONPATH=services/api. Saves a small evidence report, never credentials.
"""
import argparse
import asyncio
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from helvetic_lens.basel_stadt_connector import BaselStadtConnector
from helvetic_lens.basel_stadt_pilot import PACK_ID
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app
from helvetic_lens.models import RegulatoryDocumentVersion, RegulatoryWork
from sqlalchemy import func, select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="basel-live-", dir=args.output.parent) as directory:
        root = Path(directory)
        settings = Settings(_env_file=None, database_url="sqlite:///" + (root / "test.db").as_posix(),
                            data_dir=root / "data", app_environment="test", job_execution_mode="inline",
                            apertus_api_key="", apertus_base_url="", firecrawl_api_key="")
        app = create_app(settings)
        report = {"checked_at": datetime.now(UTC).isoformat(), "source": "https://data.bs.ch/explore/dataset/100354/", "streams": {}, "artifacts": []}
        with TestClient(app) as client:
            service = app.state.service
            activation = client.post(f"/api/source-packs/{PACK_ID}/activate")
            assert activation.status_code == 202, activation.text
            for job in activation.json()["jobs"]:
                assert asyncio.run(service.execute_job(job["id"], worker="basel-live"))["state"] == "succeeded"
            queued = service.enqueue_connector_sync(PACK_ID, "starter-de")
            completed = asyncio.run(service.execute_job(queued["job"]["id"], worker="basel-live"))
            assert completed["state"] == "succeeded", completed
            report["streams"]["starter-de"] = completed["result"]["data"]
            plan = {"name": "Basel live privacy acceptance", "goal": "Datenschutz", "concepts": ["Datenschutz"],
                    "synonyms": [], "exclusions": [], "jurisdictions": ["CH-BS"], "languages": ["de"],
                    "source_pack_ids": [PACK_ID], "document_kinds": ["act", "ordinance", "unclassified_document"],
                    "event_kinds": ["created", "new_version", "amended", "repealed", "replaced", "status_changed"], "importance_floor": "low"}
            preview = client.post("/api/monitoring-topics/preview", json=plan)
            assert preview.status_code == 200 and preview.json()["items"], preview.text
            for concept in ("Datenschutz", "Bau"):
                sample = client.post("/api/monitoring-topics/preview", json={**plan, "concepts": [concept]})
                assert sample.status_code == 200 and sample.json()["items"], sample.text
                item = sample.json()["items"][0]
                version_id = item["evidence_url"].rsplit("/", 1)[-1]
                detail = client.get(f"/api/regulatory-versions/{version_id}")
                artifact = client.get(f"/api/regulatory-versions/{version_id}/artifact")
                assert detail.status_code == artifact.status_code == 200
                assert len(artifact.content) > 100 and concept.casefold() in detail.text.casefold()
                report["artifacts"].append({"title": item["title"], "publisher_version": item["source_url"],
                                            "bytes": len(artifact.content), "sha256": hashlib.sha256(artifact.content).hexdigest(), "reopened": True})
            saved = client.post("/api/monitoring-topics", json={**plan, "idempotency_key": "basel-live-acceptance"})
            assert saved.status_code == 201, saved.text
            report["topic_saved_without_ai"] = not saved.json()["plan"]["ai_assisted"]
            with service.db.session(include_all_organizations=True) as session:
                before = session.scalar(select(func.count()).select_from(RegulatoryDocumentVersion))
            repeated = service.enqueue_connector_sync(PACK_ID, "starter-de")
            assert asyncio.run(service.execute_job(repeated["job"]["id"], worker="basel-live"))["state"] == "succeeded"
            with service.db.session(include_all_organizations=True) as session:
                assert session.scalar(select(func.count()).select_from(RegulatoryDocumentVersion)) == before == 2
                assert session.scalar(select(func.count()).select_from(RegulatoryWork)) == 2
            report["starter_overlap_deduplicated"] = True
            # Bounded actual pages, not an assertion of complete cantonal coverage.
            for stream in ("latest-de", "catalogue-de"):
                connector = BaselStadtConnector(settings, stream=stream, page_size=2)
                first = asyncio.run(connector.discover_since(None, {}))
                second = asyncio.run(connector.discover_since(first.next_cursor, {}))
                assert first.items and second.items
                assert not {r.source_revision for r in first.items} & {r.source_revision for r in second.items}
                ingested = asyncio.run(service.connector_runner.run_page(connector, stream=stream))
                assert ingested.status == "persisted", ingested.error
                report["streams"][stream] = {"discovery_pages": 2, "items": len(first.items) + len(second.items), "next_cursor": second.next_cursor,
                                              "ingested_page_status": ingested.status, "ingested_items": ingested.persisted}
        service.db.engine.dispose()
    # Job IDs are local ephemeral evidence, not useful report fields.
    report["streams"]["starter-de"] = {key: value for key, value in report["streams"]["starter-de"].items() if key in {"status", "persisted", "total", "next_cursor", "error"}}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
