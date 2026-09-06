"""Run real cache/history/job API scenarios on a separate empty local PostgreSQL."""

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
from pytest import MonkeyPatch
from test_runtime_cache import (
    bound_app,
    test_completed_jobs_reuse_only_matching_runtime,
    test_completed_work_queued_without_runtime_cannot_be_reused_as_current_offline,
    test_exact_runtime_reuses_answer_across_restart_but_new_revision_does_not,
    test_model_change_while_queued_cannot_poison_original_job_cache_key,
    test_rejected_answer_retry_preserves_failed_history,
    test_views_and_report_reuse_agree_after_model_change_and_remain_readable_offline,
)

CASES = {
    "queued-ask": (test_model_change_while_queued_cannot_poison_original_job_cache_key, "ask-jobs"),
    "queued-impact": (test_model_change_while_queued_cannot_poison_original_job_cache_key, "analyse-jobs"),
    "offline-ask": (test_completed_work_queued_without_runtime_cannot_be_reused_as_current_offline, "ask-jobs"),
    "offline-impact": (test_completed_work_queued_without_runtime_cannot_be_reused_as_current_offline, "analyse-jobs"),
    "restart-ask": (test_exact_runtime_reuses_answer_across_restart_but_new_revision_does_not, "ask"),
    "restart-impact": (test_exact_runtime_reuses_answer_across_restart_but_new_revision_does_not, "analyse"),
    "completed-ask": (test_completed_jobs_reuse_only_matching_runtime, "ask-jobs"),
    "completed-impact": (test_completed_jobs_reuse_only_matching_runtime, "analyse-jobs"),
    "failed-history": (test_rejected_answer_retry_preserves_failed_history,),
    "views": (test_views_and_report_reuse_agree_after_model_change_and_remain_readable_offline,),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--case", required=True, choices=CASES)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1"} or not (url.database or "").startswith("hl_runtime_cache_"):
        parser.error("Use a separate local PostgreSQL database named hl_runtime_cache_*, never working data.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("The scratch database must be empty; this checker never deletes existing tables.")
            version = connection.exec_driver_sql("SHOW server_version").scalar_one()
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="hl-runtime-cache-") as directory:
        settings = Settings(
            _env_file=None, database_url=args.database_url, data_dir=Path(directory),
            job_execution_mode="inline", apertus_provider="custom", apertus_base_url="",
            apertus_api_key="", firecrawl_api_key="", allow_private_sources=False,
        )
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(settings, fetcher=fetcher, model_client=model)
        try:
            with TestClient(app) as client, MonkeyPatch.context() as patch:
                fixture = bound_app.__wrapped__((client, fetcher, app.state.service, model), patch)
                check, *parameters = CASES[args.case]
                check(fixture, *parameters)
        finally:
            app.state.service.db.engine.dispose()
    print(f"PostgreSQL {version}: {args.case} passed with synthetic model transport; no real AI, mail or source calls.")


if __name__ == "__main__":
    main()
