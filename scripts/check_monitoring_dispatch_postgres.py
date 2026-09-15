"""Verify handoff behavior in an EMPTY disposable local PostgreSQL database."""

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app
from test_ai_dispatch import test_postgres_busy_dispatcher_does_not_wait_on_its_lock
from test_monitoring_dispatch import (
    test_broker_failure_retries_same_job_without_consuming_queue_turn,
    test_full_ai_window_does_not_reduce_non_ai_throughput,
    test_old_ingestion_backlog_does_not_hide_new_monitoring_handoff,
    test_postgres_locked_queue_head_leaves_outbox_available_to_owner,
    test_priority_ages_only_after_both_job_and_outbox_are_ready,
    test_scoped_non_ai_dispatch_never_hands_off_foreign_jobs,
    test_small_batches_rotate_after_restart_with_equal_clocks,
)

SUITES = {
    "legacy-prefix": test_old_ingestion_backlog_does_not_hide_new_monitoring_handoff,
    "restart": test_small_batches_rotate_after_restart_with_equal_clocks,
    "priority": test_priority_ages_only_after_both_job_and_outbox_are_ready,
    "scope": test_scoped_non_ai_dispatch_never_hands_off_foreign_jobs,
    "broker-retry": test_broker_failure_retries_same_job_without_consuming_queue_turn,
    "ai-window": test_full_ai_window_does_not_reduce_non_ai_throughput,
    "row-lock": test_postgres_locked_queue_head_leaves_outbox_available_to_owner,
    "dispatcher-lock": test_postgres_busy_dispatcher_does_not_wait_on_its_lock,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--suite", choices=SUITES, required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1"} or url.database != "hl_monitoring_dispatch":
        parser.error("Use an empty disposable local database named hl_monitoring_dispatch only.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing a database with existing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="hl-dispatch-check-") as artifacts:
        settings = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts),
            job_execution_mode="inline", apertus_provider="custom", apertus_base_url="",
            apertus_api_key="", firecrawl_api_key="")
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(settings, fetcher=fetcher, model_client=model)
        try:
            with TestClient(app) as client:
                SUITES[args.suite]((client, fetcher, app.state.service, model))
        finally:
            app.state.service.db.engine.dispose()
    print(f"PostgreSQL Monitoring handoff {args.suite}: passed; synthetic work and broker only.")


if __name__ == "__main__":
    main()
