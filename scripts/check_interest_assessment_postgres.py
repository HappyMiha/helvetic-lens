"""Run brief transaction regressions against an EMPTY disposable local database."""

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
from test_interest_assessment_store import (
    test_concurrent_reservations_and_claims_produce_one_assessment_and_one_owner,
    test_cross_org_reads_and_writes_are_rejected_even_in_privileged_session,
    test_migration_roundtrip_preserves_existing_corpus_and_matches,
    test_persisted_brief_is_reused_without_inference_and_preserves_exact_source_bindings,
    test_retry_is_explicit_bounded_and_does_not_store_provider_secrets,
    test_revised_input_supersedes_inflight_work_and_old_worker_cannot_publish,
    test_unverified_result_cannot_be_persisted,
)

SUITES = {
    "reuse": test_persisted_brief_is_reused_without_inference_and_preserves_exact_source_bindings,
    "superseded": test_revised_input_supersedes_inflight_work_and_old_worker_cannot_publish,
    "retry": test_retry_is_explicit_bounded_and_does_not_store_provider_secrets,
    "scope": test_cross_org_reads_and_writes_are_rejected_even_in_privileged_session,
    "concurrency": test_concurrent_reservations_and_claims_produce_one_assessment_and_one_owner,
    "validation": test_unverified_result_cannot_be_persisted,
    "migration": test_migration_roundtrip_preserves_existing_corpus_and_matches,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--suite", choices=SUITES, required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "hl089_regression":
        parser.error("Use an empty disposable local database named hl089_regression only.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to change a database with existing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-interest-assessment-") as artifacts:
        settings = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts),
                            job_execution_mode="inline", apertus_provider="custom", apertus_base_url="",
                            apertus_api_key="", firecrawl_api_key="")
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(settings, fetcher=fetcher, model_client=model)
        with TestClient(app) as client:
            SUITES[args.suite]((client, fetcher, app.state.service, model))
        app.state.service.db.engine.dispose()
    print(f"PostgreSQL interest assessment {args.suite}: passed; no real inference or delivery.")


if __name__ == "__main__":
    main()
