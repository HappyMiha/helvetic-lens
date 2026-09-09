"""Basel acceptance and first-use contention in an EMPTY disposable local PostgreSQL DB."""
import argparse
import concurrent.futures
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from helvetic_lens.basel_onboarding import collect
from helvetic_lens.basel_stadt_pilot import PACK_ID
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app
from helvetic_lens.models import ConnectorSchedule
from test_basel_stadt import (
    test_first_material_journey_reopens_exact_artifact_and_saves_once,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "hl080_basel_regression":
        parser.error("Use only the empty local hl080_basel_regression database.")
    engine = create_engine(url)
    with engine.connect() as connection:
        if inspect(connection).get_table_names():
            parser.error("Database is not empty; refusing to change existing data.")
    engine.dispose()
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="basel-pg-", dir=ROOT / ".tmp") as folder:
        settings = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(folder),
                            job_execution_mode="inline", apertus_provider="custom", apertus_base_url="", apertus_api_key="", firecrawl_api_key="")
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(settings, fetcher=fetcher, model_client=model)
        with TestClient(app) as client, pytest.MonkeyPatch.context() as monkeypatch:
            service = app.state.service
            test_first_material_journey_reopens_exact_artifact_and_saves_once((client, fetcher, service, model), monkeypatch)
            with service.db.session(include_all_organizations=True) as session:
                schedule = session.scalar(select(ConnectorSchedule).where(ConnectorSchedule.connector == PACK_ID, ConnectorSchedule.stream == "starter-de"))
                schedule.last_enqueued_at = None
                session.commit()
            # Different service instances have independent Python write guards.
            other = create_app(settings, fetcher=fetcher, model_client=model)
            with TestClient(other):
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(collect, [service, other.state.service]))
                assert sorted(item["state"] for item in results) == ["queued", "recently_requested"], results
            other.state.service.db.engine.dispose()
        service.db.engine.dispose()
    print("PostgreSQL Basel-Stadt: collector job/fanout, scoped preview, exact artifact reopening, duplicate topic detection, idempotent save, tenant isolation and concurrent first-use coalescing passed. No live sources or AI calls.")


if __name__ == "__main__":
    main()
