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
from pytest import MonkeyPatch
from test_digest_event_pages import (
    test_equal_time_keysets_ignore_new_admissions_and_advance_empty_filtered_pages,
)
from test_digest_periods import (
    test_period_sql_excludes_large_history_future_other_sources_and_private_states,
)
from test_digest_preview_pages import (
    test_http_preview_bounds_sparse_pages_and_save_without_mail_or_inference,
)
from test_digest_resume import (
    test_digest_yield_is_atomic_fair_and_finishes_without_new_model_calls,
)
from test_inbox_context import (
    test_comparison_and_artifact_links_use_visible_scalar_ids_only,
    test_context_queries_do_not_grow_between_one_and_fifty_event_pages,
    test_successor_aliases_prefer_current_organization_watch_without_foreign_state,
)
from test_inbox_history_batches import (
    test_page_selects_histories_in_four_queries_with_bounded_payloads,
)
from test_inbox_history_bounds import (
    check_history_index_roundtrip,
    test_large_history_reads_only_latest_and_current_payloads,
)
from test_inbox_navigation import (
    test_options_remain_available_outside_page_and_limit_without_loading_laws,
)
from test_inbox_page_api import (
    test_public_pages_have_stable_equal_time_order_and_only_hydrate_selected_events,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--suite", choices=("history", "periods", "pages", "resume", "inbox", "options", "batches", "context", "links", "successors", "preview"), default="history")
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
            harness = (client, fetcher, service, model)
            if args.suite == "preview":
                with MonkeyPatch.context() as patch:
                    test_http_preview_bounds_sparse_pages_and_save_without_mail_or_inference(harness, patch)
                print("PostgreSQL: authenticated digest save/preview traverse 121 events in 50/50/21 pages, including two empty severity pages; stable first/back period, legacy compatibility, no read-state/job/delivery writes, AI or mail calls.")
                return
            if args.suite == "context":
                test_context_queries_do_not_grow_between_one_and_fifty_event_pages(harness)
                print("PostgreSQL: one- and 50-event HTTP pages both execute 16 SELECTs; no Law, Version, Comparison or RegulatoryDocumentVersion ORM payloads loaded. No AI or mail calls.")
                return
            if args.suite == "links":
                test_comparison_and_artifact_links_use_visible_scalar_ids_only(harness)
                print("PostgreSQL: stable latest visible comparison and artifact links use scalar IDs; large document/diff bodies and foreign-owned links are excluded.")
                return
            if args.suite == "successors":
                test_successor_aliases_prefer_current_organization_watch_without_foreign_state(harness)
                print("PostgreSQL: successor alias ranking prefers current-organization active/paused watches then oldest visible mapping; foreign watch state is never borrowed.")
                return
            if args.suite == "batches":
                test_page_selects_histories_in_four_queries_with_bounded_payloads(harness)
                print("PostgreSQL: 50-event inbox page reads 7,474 historical analysis/review rows with 4 selection/hydration queries and 111 materialized records; current conclusions, failed attempts, legacy output and latest human decisions remain correct. No AI or mail calls.")
                return
            if args.suite == "options":
                test_options_remain_available_outside_page_and_limit_without_loading_laws(harness)
                print("PostgreSQL: independent 50-law scalar search, selected item beyond the limit, literal wildcard escaping, paused watches and organization isolation pass without hydrating Law/DocumentWatch models.")
                return
            if args.suite == "inbox":
                test_public_pages_have_stable_equal_time_order_and_only_hydrate_selected_events(harness)
                print("PostgreSQL: public inbox API traverses 121 equal-time events in 50/50/21 pages, with exactly two selected event/delivery payloads per event, stable cursors and page-only counts. No AI or mail calls.")
                return
            if args.suite == "resume":
                with MonkeyPatch.context() as patch:
                    test_digest_yield_is_atomic_fair_and_finishes_without_new_model_calls(harness, patch)
                print("PostgreSQL: digest preparation yields after 50 events, dispatches another recipient first, resumes to 61 without duplicate events and sends once through a mail double. No AI or real email calls.")
                return
            if args.suite == "pages":
                with MonkeyPatch.context() as patch:
                    test_equal_time_keysets_ignore_new_admissions_and_advance_empty_filtered_pages(harness, patch)
                print("PostgreSQL: 121 equal-time event keys traversed without duplication or omission; empty presentation pages advance; a concurrently admitted event waits for the next traversal. No AI or mail calls.")
                return
            if args.suite == "periods":
                test_period_sql_excludes_large_history_future_other_sources_and_private_states(harness)
                print("PostgreSQL: 10,000 archived events excluded before payload hydration; half-open period, source filters, private states, tenant isolation and column-only source options passed. No AI or mail calls.")
                return
            test_large_history_reads_only_latest_and_current_payloads(harness)
            with service.db.session() as session:
                delivery_id = session.scalar(select(OrganizationRelationCandidate.id))
            check_history_index_roundtrip(service, delivery_id)
            print("PostgreSQL: 10,001 saved analyses selected with 3 queries and 2 materialized payloads; actual inbox, stable ties, failed-latest fallback and populated index migration passed. No AI calls.")


if __name__ == "__main__":
    main()
