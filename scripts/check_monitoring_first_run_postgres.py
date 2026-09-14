"""Rehearse first-run migration and concurrent choice on an empty local scratch DB."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from helvetic_lens import onboarding
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app
from helvetic_lens.models import UserOnboarding
from test_monitoring_first_run import (
    test_additive_migration_preserves_legacy_intent_and_rejects_customs,
    test_nine_choices_retry_defer_resume_and_legacy_return_are_only_personal_intent,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if (url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"}
            or url.database != "helvetic_first_run_check"):
        parser.error("Use only an empty localhost helvetic_first_run_check database.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to modify a database containing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-first-run-") as artifacts:
        settings = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts),
            job_execution_mode="inline", apertus_provider="custom", apertus_base_url="", apertus_api_key="", firecrawl_api_key="")
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(settings, fetcher=fetcher, model_client=model)
        with TestClient(app) as client:
            service = app.state.service
            gate = Barrier(2)

            def choose(_):
                with service.db.session() as session:
                    gate.wait(timeout=10)
                    return onboarding.save(session, service.organization_id, "anonymous-development", None,
                        "monitoring", monitoring_template="pollen")

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(choose, (1, 2)))
            assert results[0] == results[1] and results[0]["monitoring_template"] == "pollen"
            with service.db.session() as session:
                assert session.scalar(select(func.count()).select_from(UserOnboarding)) == 1
            harness = (client, fetcher, service, model)
            test_additive_migration_preserves_legacy_intent_and_rejects_customs(harness)
            test_nine_choices_retry_defer_resume_and_legacy_return_are_only_personal_intent(harness)
        service.db.engine.dispose()
    print("PostgreSQL first run: simultaneous duplicate choice, real downgrade/upgrade preservation, database C4 rejection and all-nine personal intent checks passed.")


if __name__ == "__main__":
    main()
