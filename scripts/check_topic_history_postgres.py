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
from helvetic_lens import jobs, topic_matching
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    Job,
    MonitoringTopic,
    Organization,
    RegulatoryEvent,
    RegulatoryEventState,
)
from test_topic_history import (
    test_501_events_resume_through_outbox_without_duplicates_or_model_calls,
)
from test_topic_live import (
    seed_topics,
    test_51_matching_topics_resume_after_write_limit_and_retain_metadata_matches,
)
from test_topic_preview_parity import (
    test_preview_history_and_live_share_decision_reasons_and_confidence,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--suite", choices=("history", "live", "preview"), default="history")
    args = parser.parse_args()
    value = args.database_url
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
            if args.suite == "preview":
                test_preview_history_and_live_share_decision_reasons_and_confidence(
                    (client, fetcher, service, model), "Federal publication",
                    {"concepts": ["RS 141.0"], "synonyms": []}, True, "official_identifier",
                )
                print("PostgreSQL: scoped preview and history/live activation share exact official-reference signals and confidence, with zero AI calls.")
                return
            regression = (
                test_51_matching_topics_resume_after_write_limit_and_retain_metadata_matches
                if args.suite == "live" else test_501_events_resume_through_outbox_without_duplicates_or_model_calls
            )
            regression((client, fetcher, service, model))
            print(f"PostgreSQL: {args.suite} cursor, outbox continuation, no duplicate matches and zero AI calls passed.")

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
                    select(Job).where(Job.type == ("topic_match_event" if args.suite == "live" else "topic_match_backfill"))
                )
                job_id = job.id
                topic_id = session.scalar(select(MonitoringTopic.id)) if args.suite == "live" else job.target_id
                live_payload = dict(job.payload)
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
            if args.suite == "history":
                assert client.get(f"/api/monitoring-topics/{topic_id}").json()["history_scan"]["processed"] == 501
            else:
                assert client.get(f"/api/jobs/{job_id}").json()["progress"]["current"] == 51
            print("PostgreSQL: plan lock and completed-checkpoint replay passed.")

            if args.suite == "live":
                event_id = live_payload["event_id"]
                with service.db.session() as batch, service.db.session() as edit:
                    # Exercise the actual joined query, not merely a manually held lock.
                    data = topic_matching.run_live_batch(
                        batch, event_id, service.settings,
                        admission_id=live_payload["admission_id"],
                        evidence_fingerprint=live_payload["evidence_fingerprint"],
                    )
                    assert data["processed"] == 20 and data["remaining"] == 31
                    locked = batch.scalar(select(MonitoringTopic).where(MonitoringTopic.id == data["cursor"]))
                    assert edit.scalar(select(MonitoringTopic).where(MonitoringTopic.id == locked.id)
                                       .with_for_update(skip_locked=True)) is None
                with service.db.session(include_all_organizations=True) as session:
                    for index in range(100):
                        org = Organization(name=f"Live PG {index}", slug=f"live-pg-{index}")
                        session.add(org)
                        session.flush()
                        session.add(RegulatoryEventState(organization_id=org.id, event_id=event_id))
                        seed_topics(session, org.id, 1, concepts=["rare citizenship subject"], synonyms=[])
                    result = topic_matching.enqueue_live_events(
                        session, [session.get(RegulatoryEvent, event_id)], service.settings
                    )
                    assert result["organizations_considered"] == 101 and result["queued"] == 100
                    assert result["reused"] == 1
                    last = session.scalar(select(Job).where(Job.type == "topic_match_event")
                                          .order_by(Job.organization_id.desc()))
                    owner, last_id = last.organization_id, last.id
                    session.commit()
                with service.db.organization_context(owner):
                    result = asyncio.run(service.execute_job(last_id))
                    assert result["state"] == "succeeded" and result["result"]["data"]["matched"] == 1
                assert client.get(f"/api/jobs/{last_id}").status_code == 404
                assert model.calls == []
                print("PostgreSQL: actual live batch locks, 101-organization spooling and tenant worker isolation passed.")


if __name__ == "__main__":
    main()
