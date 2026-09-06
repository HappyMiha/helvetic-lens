"""Run real history-page regressions on an empty, named localhost scratch database."""

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
from test_document_history_pages import (
    test_complete_history_pages_are_bounded_and_keep_equal_time_order,
    test_cursor_survives_boundary_deletion_and_excludes_new_saves,
    test_first_cursor_includes_exact_cutoff_without_id_collation_sentinel,
    test_history_indexes_migrate_without_rewriting_evidence,
    test_history_pages_recheck_watch_and_private_evidence_even_when_privileged,
    test_paged_document_detail_opt_in_keeps_current_version_and_legacy_contract,
)

CASES = (
    "versions",
    "comparisons",
    "observations",
    "detail",
    "deletion",
    "scope",
    "migration",
    "cutoff",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--case", required=True, choices=CASES)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database != f"hl099_history_{args.case}"
    ):
        parser.error(
            "Use only the named empty localhost scratch database for this case."
        )
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to modify a database containing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="hl-document-history-") as artifacts:
        config = Settings(
            _env_file=None,
            database_url=args.database_url,
            data_dir=Path(artifacts),
            job_execution_mode="inline",
            apertus_provider="custom",
            apertus_base_url="",
            apertus_api_key="",
            firecrawl_api_key="",
        )
        fetcher, model = FakeFetcher(), ScriptedModel()
        app = create_app(config, fetcher=fetcher, model_client=model)
        with TestClient(app) as client:
            harness = (client, fetcher, app.state.service, model)
            if args.case in CASES[:3]:
                test_complete_history_pages_are_bounded_and_keep_equal_time_order(
                    harness, args.case
                )
            elif args.case == "cutoff":
                with MonkeyPatch.context() as patch:
                    test_first_cursor_includes_exact_cutoff_without_id_collation_sentinel(harness, patch)
            else:
                {
                    "detail": test_paged_document_detail_opt_in_keeps_current_version_and_legacy_contract,
                    "deletion": test_cursor_survives_boundary_deletion_and_excludes_new_saves,
                    "scope": test_history_pages_recheck_watch_and_private_evidence_even_when_privileged,
                    "migration": test_history_indexes_migrate_without_rewriting_evidence,
                }[args.case](harness)
            print(
                f"PostgreSQL document history: {args.case} passed on synthetic data; no source/model calls."
            )


if __name__ == "__main__":
    main()
