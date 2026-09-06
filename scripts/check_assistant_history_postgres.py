"""Run private-history regressions only on named empty localhost scratch databases."""
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
from test_assistant_history import (
    test_delete_preserves_shared_evidence_and_old_context_requires_new_id,
    test_in_flight_model_response_cannot_recreate_deleted_conversation,
    test_metadata_pages_are_bounded_read_only_and_have_no_private_bodies,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--case", required=True, choices=("metadata", "deletion", "race"))
    args = parser.parse_args()
    url = make_url(args.database_url)
    if (url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"}
            or url.database != f"hl083_history_{args.case}"):
        parser.error("Use only the named empty localhost scratch database for this case.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to modify a database containing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="hl-assistant-history-") as artifacts:
        config = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts),
            job_execution_mode="inline", apertus_provider="custom", apertus_base_url="", apertus_api_key="", firecrawl_api_key="")
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(config, fetcher=fetcher, model_client=model)
        with TestClient(app) as client:
            harness = (client, fetcher, app.state.service, model)
            if args.case == "metadata":
                test_metadata_pages_are_bounded_read_only_and_have_no_private_bodies(harness)
            elif args.case == "deletion":
                test_delete_preserves_shared_evidence_and_old_context_requires_new_id(harness)
            else:
                with MonkeyPatch.context() as patch:
                    test_in_flight_model_response_cannot_recreate_deleted_conversation(harness, patch)
            print(f"PostgreSQL personal history: {args.case} passed on synthetic data; no provider calls.")


if __name__ == "__main__":
    main()
