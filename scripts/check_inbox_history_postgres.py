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
from test_corpus_evidence import (
    test_native_connector_roundtrip_reads_saved_text_and_safe_original_without_legacy_copy,
    test_native_evidence_cannot_bypass_scope_even_in_privileged_session,
    test_relation_delivery_grants_source_evidence_without_direct_watch_or_topic_admission,
)
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
from test_evidence_navigation import (
    test_event_surfaces_share_exact_evidence_and_revocation_guards,
)
from test_feed_evidence import (
    test_exact_event_link_reaches_old_event_and_remains_scoped,
    test_topic_only_artifact_is_exact_visible_version_without_body_hydration,
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
from test_interest_feed import (
    test_direct_watched_document_event_is_retained_without_topics_or_relation_candidates,
    test_equal_time_cursor_covers_all_events_and_binds_filters_and_principal,
    test_one_card_for_multiple_topics_and_law_without_ai,
)
from test_relation_configuration_freshness import (
    test_configuration_changes_remove_current_conclusion_without_jobs_or_history_rewrite,
    test_digest_restarts_configuration_selection_and_rejects_old_prepared_delivery,
)
from test_relation_profile_freshness import (
    test_profile_edit_invalidates_history_inbox_and_severity_without_spending_tokens,
)
from test_relation_prompt_freshness import (
    test_digest_prompt_change_restarts_selection_and_never_sends_old_selection,
    test_used_prompt_edit_invalidates_history_and_inbox_without_new_inference,
)
from test_relation_version_freshness import (
    test_changed_or_removed_version_invalidates_current_without_rewriting_history,
    test_final_digest_read_drops_obsolete_ai_severity_without_sending,
)
from test_topic_reviews import (
    test_postgres_concurrent_reviews_do_not_overwrite_or_duplicate,
    test_review_hides_topic_feed_match_but_preserves_evidence_and_personal_state,
    test_review_migration_roundtrip_preserves_existing_match_evidence,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--suite", choices=("history", "periods", "pages", "resume", "inbox", "options", "batches", "context", "links", "successors", "preview", "profile", "configuration", "configuration-digest", "prompts", "prompts-digest", "versions", "versions-digest", "feed", "feed-pages", "feed-watch", "topic-reviews", "topic-review-migration", "topic-review-race", "topic-review-retry", "feed-evidence", "feed-private-evidence", "feed-event-link", "native-evidence", "native-evidence-private", "native-evidence-relation", "evidence-navigation", "evidence-navigation-legacy", "evidence-navigation-private", "evidence-navigation-revoked"), default="history")
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
            if args.suite.startswith("evidence-navigation"):
                condition = {"evidence-navigation": None, "evidence-navigation-legacy": "legacy",
                             "evidence-navigation-private": "foreign_law", "evidence-navigation-revoked": "revoked"}[args.suite]
                test_event_surfaces_share_exact_evidence_and_revocation_guards(harness, condition)
                print("PostgreSQL: registry, inbox and Today share exact native/legacy evidence links and access guards without body hydration.")
                return
            if args.suite == "native-evidence":
                test_native_connector_roundtrip_reads_saved_text_and_safe_original_without_legacy_copy(harness)
                print("PostgreSQL: native connector ingestion, saved text and safe original response work without creating legacy copies.")
                return
            if args.suite == "native-evidence-private":
                test_native_evidence_cannot_bypass_scope_even_in_privileged_session(harness, "private")
                print("PostgreSQL: private native work remains inaccessible despite an organization event admission.")
                return
            if args.suite == "native-evidence-relation":
                test_relation_delivery_grants_source_evidence_without_direct_watch_or_topic_admission(harness)
                print("PostgreSQL: relation-delivered source evidence opens without a direct watch; delivery removal revokes access.")
                return
            if args.suite in {"feed-evidence", "feed-private-evidence"}:
                test_topic_only_artifact_is_exact_visible_version_without_body_hydration(harness, "foreign_version" if args.suite == "feed-private-evidence" else None)
                print("PostgreSQL: exact event artifact lookup respects private version ownership without document-body hydration.")
                return
            if args.suite == "feed-event-link":
                test_exact_event_link_reaches_old_event_and_remains_scoped(harness)
                print("PostgreSQL: direct older-event feed navigation respects scope, cursor binding and admission revocation.")
                return
            if args.suite == "topic-reviews":
                test_review_hides_topic_feed_match_but_preserves_evidence_and_personal_state(harness)
                print("PostgreSQL: shared topic review excludes/restores the exact feed match while retaining evidence and personal state.")
                return
            if args.suite == "topic-review-migration":
                test_review_migration_roundtrip_preserves_existing_match_evidence(harness)
                print("PostgreSQL: topic-review migration roundtrip preserves existing match evidence and restores history index.")
                return
            if args.suite in {"topic-review-race", "topic-review-retry"}:
                test_postgres_concurrent_reviews_do_not_overwrite_or_duplicate(harness, args.suite == "topic-review-retry")
                print("PostgreSQL: concurrent topic review sessions preserve one decision without overwriting or duplicate retries.")
                return
            if args.suite == "feed-watch":
                test_direct_watched_document_event_is_retained_without_topics_or_relation_candidates(harness)
                print("PostgreSQL: direct active-watch updates stay in the feed without any topic or law-relation candidate; paused watches stop admitting them.")
                return
            if args.suite == "feed":
                test_one_card_for_multiple_topics_and_law_without_ai(harness)
                print("PostgreSQL: one event across two current topics and a watched law, source links and no inference.")
                return
            if args.suite == "feed-pages":
                test_equal_time_cursor_covers_all_events_and_binds_filters_and_principal(harness)
                print("PostgreSQL: equal-time feed keyset pages cover every event without duplicates and bind account/filters.")
                return
            if args.suite == "versions":
                test_changed_or_removed_version_invalidates_current_without_rewriting_history(harness, "target", False)
                print("PostgreSQL: changed candidate document version excludes obsolete history/inbox applicability while preserving citations, counts and history payloads without inference.")
                return
            if args.suite == "versions-digest":
                with MonkeyPatch.context() as patch:
                    test_final_digest_read_drops_obsolete_ai_severity_without_sending(harness, patch)
                print("PostgreSQL: final digest read drops a prepared event whose AI-only severity became stale after document-version change; no mail is sent.")
                return
            if args.suite == "prompts":
                test_used_prompt_edit_invalidates_history_and_inbox_without_new_inference(harness, "impact_instructions")
                print("PostgreSQL: used prompt edit invalidates current relation history and inbox without inference, jobs or rewriting saved evidence.")
                return
            if args.suite == "prompts-digest":
                with MonkeyPatch.context() as patch:
                    test_digest_prompt_change_restarts_selection_and_never_sends_old_selection(harness, patch)
                print("PostgreSQL: platform prompt edit restarts bounded digest preparation and rejects completed stale selection without sending mail.")
                return
            if args.suite == "configuration":
                test_configuration_changes_remove_current_conclusion_without_jobs_or_history_rewrite(harness, "apertus_model", "new-model")
                print("PostgreSQL: model change invalidates history and both inbox readers without inference or history rewrites; original configuration restores the valid saved report.")
                return
            if args.suite == "configuration-digest":
                with MonkeyPatch.context() as patch:
                    test_digest_restarts_configuration_selection_and_rejects_old_prepared_delivery(harness, patch)
                print("PostgreSQL: persisted model settings invalidate completed digest selection and restart bounded preparation without sending mail or calling AI.")
                return
            if args.suite == "profile":
                test_profile_edit_invalidates_history_inbox_and_severity_without_spending_tokens(harness)
                print("PostgreSQL: profile edit immediately invalidates current history, legacy/paged inbox and severity; retained evidence stays accessible, with no read-time inference, jobs or history rewrites.")
                return
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
