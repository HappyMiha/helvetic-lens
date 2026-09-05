"""Verify bounded inbox history reads on an empty disposable local PostgreSQL DB."""

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app
from helvetic_lens.models import OrganizationRelationCandidate
from test_inbox_history_bounds import (
    check_history_index_roundtrip,
    test_large_history_reads_only_latest_and_current_payloads,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "hl099_regression":
        parser.error("Use an empty disposable local database named hl099_regression only.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to change a database with existing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-inbox-history-") as artifacts:
        settings = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts),
                            job_execution_mode="inline", apertus_provider="custom", apertus_base_url="",
                            apertus_api_key="", firecrawl_api_key="")
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(settings, fetcher=fetcher, model_client=model)
        with TestClient(app) as client:
            service = app.state.service
            test_large_history_reads_only_latest_and_current_payloads((client, fetcher, service, model))
            with service.db.session() as session:
                delivery_id = session.scalar(select(OrganizationRelationCandidate.id))
            check_history_index_roundtrip(service, delivery_id)
            print("PostgreSQL: 10,001 saved analyses selected with 3 queries and 2 materialized payloads; actual inbox, stable ties, failed-latest fallback and populated index migration passed. No AI calls.")


if __name__ == "__main__":
    main()
