"""Run against an empty, disposable PostgreSQL database, never an app database.

Example: python scripts/check_topic_history_postgres.py --database-url
postgresql+psycopg://hl094:local-test-only@127.0.0.1:15494/hl094_regression
"""

import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from alembic import command
from alembic.config import Config
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from helvetic_lens import jobs
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.main import create_app
from helvetic_lens.models import Job, MonitoringTopic
from test_topic_history import (
    test_501_events_resume_through_outbox_without_duplicates_or_model_calls,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    value = parser.parse_args().database_url
    url = make_url(value)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database != "hl094_regression"
    ):
        parser.error("Use the empty local disposable hl094_regression database only.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error(
                    "The database is not empty. Refusing to alter existing data."
                )
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-topic-history-") as artifacts:
        settings = Settings(
            _env_file=None,
            database_url=value,
            data_dir=Path(artifacts),
            job_execution_mode="inline",
            apertus_provider="custom",
            apertus_base_url="",
            apertus_api_key="",
            firecrawl_api_key="",
        )
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(settings, fetcher=fetcher, model_client=model)
        with TestClient(app) as client:
            service = app.state.service
            test_501_events_resume_through_outbox_without_duplicates_or_model_calls(
                (client, fetcher, service, model)
            )
            print(
                "PostgreSQL: 501 events, tied cursors, outbox continuation, no duplicate matches and zero AI calls passed."
            )

            config = Config(str(ROOT / "services/api/alembic.ini"))
            config.set_main_option(
                "script_location", str(ROOT / "services/api/alembic")
            )
            with service.db.engine.begin() as connection:
                config.attributes["connection"] = connection
                command.downgrade(config, "f6a2c91d7e40")
                assert "ix_regulatory_event_state_history" not in {
                    item["name"]
                    for item in inspect(connection).get_indexes(
                        "regulatory_event_states"
                    )
                }
                command.upgrade(config, "head")
                assert "ix_regulatory_event_state_history" in {
                    item["name"]
                    for item in inspect(connection).get_indexes(
                        "regulatory_event_states"
                    )
                }
            print(
                "PostgreSQL: history index downgrade/upgrade preserves the populated database."
            )

            with service.db.session() as session:
                job = session.scalar(
                    select(Job).where(Job.type == "topic_match_backfill")
                )
                job_id, topic_id = job.id, job.target_id
                job.state, job.lease_owner = "running", "batch-worker"
                job.heartbeat_at = utcnow() - timedelta(minutes=10)
                session.commit()
            with service.db.session() as batch, service.db.session() as recovery:
                batch.scalar(select(Job).where(Job.id == job_id).with_for_update())
                assert jobs.reconcile(recovery, lease_seconds=60)["recovered"] == 0
                recovery.commit()
            with service.db.session() as recovery:
                assert jobs.reconcile(recovery, lease_seconds=60)["recovered"] == 1
                recovery.commit()
            print(
                "PostgreSQL: reconciler skips an active locked batch and recovers it after the lock is released."
            )

            # A changed plan cannot commit halfway through a history batch.
            with service.db.session() as batch, service.db.session() as edit:
                batch.scalar(
                    select(MonitoringTopic)
                    .where(MonitoringTopic.id == topic_id)
                    .with_for_update()
                )
                assert (
                    edit.scalar(
                        select(MonitoringTopic)
                        .where(MonitoringTopic.id == topic_id)
                        .with_for_update(skip_locked=True)
                    )
                    is None
                )
            assert asyncio.run(service.execute_job(job_id))["state"] == "succeeded"
            assert (
                client.get(f"/api/monitoring-topics/{topic_id}").json()["history_scan"][
                    "processed"
                ]
                == 501
            )
            print("PostgreSQL: plan lock and completed-checkpoint replay passed.")


if __name__ == "__main__":
    main()
