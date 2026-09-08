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
from test_digest_schedule import (
    test_local_schedule_save_retry_legacy_omission_and_clear,
    test_schedule_migration_preserves_existing_preferences,
)
from test_evidence_navigation import (
    test_event_surfaces_share_exact_evidence_and_revocation_guards,
)
from test_feed_evidence import (
    test_exact_event_link_reaches_old_event_and_remains_scoped,
    test_topic_only_artifact_is_exact_visible_version_without_body_hydration,
)
from test_feed_topic_pages import (
    test_sparse_topic_batches_never_hide_later_valid_matches,
    test_topic_page_scope_revocation_and_cursor_kind,
)
from test_feed_watch_pages import (
    test_large_watch_fanout_is_complete_bounded_and_does_not_hydrate_laws,
    test_watch_cursor_rechecks_visibility_and_excludes_late_watches,
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
from test_monitoring_answer_context import (
    test_answer_context_checks_all_owners_even_in_privileged_session,
    test_saved_answer_context_keeps_question_and_comparison_without_new_inference_or_writes,
)
from test_monitoring_assistant_context import (
    test_personal_context_fails_closed_for_wrong_owner_role_or_unavailable_message,
    test_personal_message_context_reads_selected_user_text_without_sharing_or_inference,
)
from test_monitoring_context import (
    test_context_to_topic_preview_and_explicit_activation_reuses_existing_lifecycle,
    test_native_event_context_uses_saved_title_and_artifact_without_automatic_monitoring,
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
from test_topic_coverage import (
    test_custom_schedule_partial_health_and_old_success_are_separate_saved_facts,
    test_one_and_all_packs_use_four_scalar_queries_without_diagnostic_hydration,
    test_privileged_preview_does_not_borrow_other_organization_subscription,
    test_unscheduled_unsubscribed_preview_remains_read_only_without_inference,
)
from test_topic_duplicates import (
    test_privileged_query_still_checks_both_topic_and_revision_owners,
    test_rule_warning_is_read_only_case_order_insensitive_and_excludes_self,
    test_warning_reads_at_most_501_current_scalar_rules_and_discloses_both_limits,
)
from test_topic_reviews import (
    test_postgres_concurrent_reviews_do_not_overwrite_or_duplicate,
    test_review_hides_topic_feed_match_but_preserves_evidence_and_personal_state,
    test_review_migration_roundtrip_preserves_existing_match_evidence,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--suite", choices=("saved-analysis-current", "saved-analysis-fallback", "saved-analysis-boundary", "saved-analysis-analysis", "saved-analysis-comparison", "saved-analysis-law", "timeline-metadata", "timeline-cursor", "timeline-cutoff", "reprocess-noop", "reprocess-terminal", "reprocess-concurrent", "reprocess-positive", "reprocess-negative", "reprocess-batches", "reprocess-rollback", "reprocess-rule-change", "reprocess-admissions", "reprocess-versions", "runtime-concurrent", "runtime-current", "runtime-stale", "runtime-offline", "runtime-digest", "runtime-scope", "runtime-worker-change", "evidence-revisions-private", "evidence-revisions-prepare", "evidence-revisions-text", "evidence-revisions-metadata", "evidence-revisions-official", "evidence-revisions-noop", "evidence-revisions-legacy", "evidence-revisions-migration", "evidence-revisions-race", "evidence-revisions-digest", "law-history-large", "law-history-scope", "law-history-empty", "law-history-null", "law-history-int", "law-history-fraction", "timeline-large", "timeline-relations", "timeline-private", "timeline-law", "timeline-watch", "timeline-mapping", "timeline-work", "relation-endpoints-source", "relation-endpoints-target", "relation-endpoints-reverse", "relation-endpoints-digest", "official-relation-fields", "official-relation-links", "official-relation-retry", "official-relation-digest", "registry-details", "registry-detail-scope", "registry-detail-dates", "monitored-pages", "monitored-search", "monitored-read", "monitored-scope", "monitored-dates", "monitored-comparison", "monitored-migration", "registry-watches", "registry-events", "registry-search", "registry-dates", "registry-scope", "registry-migration", "digest-quiet-resume", "digest-quiet-unsubscribe", "digest-quiet-boundary", "digest-quiet-save", "digest-local-schedule", "digest-schedule-migration", "feed-topic-sparse", "feed-topic-scope", "feed-watch-pages", "feed-watch-scope", "evidence-pages", "evidence-pages-native", "evidence-text-pages", "source-review", "source-review-scope", "source-review-migration", "milestone-native", "milestone-migration", "milestone-race", "feed-readiness-history", "feed-readiness-bounds", "feed-readiness-sources", "onboarding-state", "onboarding-migration", "onboarding-race", "assistant-context", "assistant-context-private", "answer-context", "answer-context-private", "topic-coverage-empty", "topic-coverage-state", "topic-coverage-scope", "topic-coverage-bounds", "topic-duplicates", "topic-duplicates-scope", "topic-duplicates-bounds", "history", "periods", "pages", "resume", "inbox", "options", "batches", "context", "links", "successors", "preview", "profile", "configuration", "configuration-digest", "prompts", "prompts-digest", "versions", "versions-digest", "feed", "feed-pages", "feed-watch", "topic-reviews", "topic-review-migration", "topic-review-race", "topic-review-retry", "feed-evidence", "feed-private-evidence", "feed-event-link", "native-evidence", "native-evidence-private", "native-evidence-relation", "evidence-navigation", "evidence-navigation-legacy", "evidence-navigation-private", "evidence-navigation-revoked", "monitoring-context", "monitoring-context-activate"), default="history")
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
            if args.suite.startswith("reprocess-"):
                from test_relation_reprocessing import (
                    test_batches_resume_after_cancel_and_never_hydrate_archived_documents,
                    test_changed_code_rule_is_stale_before_reprocessing_and_preview_is_non_destructive,
                    test_changed_selected_document_version_invalidates_result_without_loading_body,
                    test_concurrent_request_id_reuses_one_maintenance_job,
                    test_current_unchanged_pair_keeps_usable_report_without_bookkeeping_invalidation,
                    test_failed_batch_rolls_back_changes_and_cursor_together,
                    test_generic_old_lead_is_rejected_without_deleting_history_or_notifications,
                    test_new_rule_supersedes_partial_job_without_touching_remaining_candidates,
                    test_operator_terminal_candidate_is_counted_but_not_rewritten,
                    test_resume_excludes_late_admissions_and_reports_deleted_candidates,
                )
                with MonkeyPatch.context() as patch:
                    if args.suite == "reprocess-noop":
                        test_current_unchanged_pair_keeps_usable_report_without_bookkeeping_invalidation(harness)
                    elif args.suite == "reprocess-terminal":
                        test_operator_terminal_candidate_is_counted_but_not_rewritten(harness, "rejected")
                    elif args.suite == "reprocess-concurrent":
                        test_concurrent_request_id_reuses_one_maintenance_job(harness)
                    elif args.suite == "reprocess-positive":
                        test_changed_code_rule_is_stale_before_reprocessing_and_preview_is_non_destructive(harness, patch)
                    elif args.suite == "reprocess-negative":
                        test_generic_old_lead_is_rejected_without_deleting_history_or_notifications(harness)
                    elif args.suite == "reprocess-batches":
                        test_batches_resume_after_cancel_and_never_hydrate_archived_documents(harness, patch)
                    elif args.suite == "reprocess-rollback":
                        test_failed_batch_rolls_back_changes_and_cursor_together(harness, patch)
                    elif args.suite == "reprocess-rule-change":
                        test_new_rule_supersedes_partial_job_without_touching_remaining_candidates(harness, patch)
                    elif args.suite == "reprocess-versions":
                        test_changed_selected_document_version_invalidates_result_without_loading_body(harness)
                    else:
                        test_resume_excludes_late_admissions_and_reports_deleted_candidates(harness)
                print("PostgreSQL:", args.suite, "passed without model, source or mail calls.")
                return
            if args.suite.startswith("runtime-"):
                from test_relation_runtime import (
                    configure_local_relation,
                    test_concurrent_offline_requests_coalesce_across_worker_guards,
                    test_digest_preparation_restarts_and_final_delivery_rejects_changed_runtime,
                    test_digest_worker_observes_again_before_delivery,
                    test_offline_reads_keep_history_and_citations_but_never_promote_or_reuse_finished_job,
                    test_runtime_observation_cannot_cross_organization_or_configuration,
                    test_same_identity_restart_reuses_job_and_keeps_original_provenance,
                    test_same_name_different_runtime_hides_old_conclusion_without_new_inference,
                )
                with MonkeyPatch.context() as patch:
                    bound = configure_local_relation(harness, patch)
                    if args.suite == "runtime-concurrent":
                        test_concurrent_offline_requests_coalesce_across_worker_guards(bound)
                    elif args.suite == "runtime-current":
                        test_same_identity_restart_reuses_job_and_keeps_original_provenance(bound)
                    elif args.suite == "runtime-stale":
                        test_same_name_different_runtime_hides_old_conclusion_without_new_inference(bound, "tokenizer_sha256")
                    elif args.suite == "runtime-offline":
                        test_offline_reads_keep_history_and_citations_but_never_promote_or_reuse_finished_job(bound)
                    elif args.suite == "runtime-digest":
                        test_digest_preparation_restarts_and_final_delivery_rejects_changed_runtime(bound, patch)
                    elif args.suite == "runtime-worker-change":
                        test_digest_worker_observes_again_before_delivery(bound, patch, True)
                    else:
                        test_runtime_observation_cannot_cross_organization_or_configuration(bound)
                print("PostgreSQL:", args.suite, "passed with synthetic HTTP/model/mail only.")
                return
            if args.suite.startswith("evidence-revisions-"):
                from test_relation_evidence_freshness import (
                    test_correction_during_generation_is_saved_as_stale_history,
                    test_correction_during_preparation_does_not_bind_old_text_to_new_revision,
                    test_digest_final_read_drops_corrected_ai_evidence_without_sending,
                    test_evidence_migration_roundtrip_preserves_history_without_counter_resurrection,
                    test_foreign_legacy_revision_is_not_exposed_in_binding,
                    test_legacy_fallback_corrections_cannot_hide_behind_corpus_version_id,
                    test_same_id_correction_invalidates_all_current_reads,
                    test_same_value_and_operational_updates_preserve_revision_and_cached_analysis,
                )
                variant = args.suite.removeprefix("evidence-revisions-")
                if variant in {"text", "metadata", "official"}:
                    name, field, value = {
                        "text": ("source_version", "text", "Corrected source text; the old hash is unchanged"),
                        "metadata": ("target_work", "metadata_json", {"scope": "Corrected scope"}),
                        "official": ("official_relation", "evidence_json", {"notice": "Corrected official evidence"}),
                    }[variant]
                    test_same_id_correction_invalidates_all_current_reads(harness, name, field, value)
                elif variant == "noop":
                    test_same_value_and_operational_updates_preserve_revision_and_cached_analysis(harness)
                elif variant == "legacy":
                    test_legacy_fallback_corrections_cannot_hide_behind_corpus_version_id(harness)
                elif variant == "private":
                    test_foreign_legacy_revision_is_not_exposed_in_binding(harness)
                elif variant == "migration":
                    test_evidence_migration_roundtrip_preserves_history_without_counter_resurrection(harness)
                else:
                    with MonkeyPatch.context() as patch:
                        if variant == "prepare":
                            test_correction_during_preparation_does_not_bind_old_text_to_new_revision(harness, patch)
                        elif variant == "race":
                            test_correction_during_generation_is_saved_as_stale_history(harness, patch)
                        else:
                            test_digest_final_read_drops_corrected_ai_evidence_without_sending(harness, patch)
                print("PostgreSQL:", args.suite, "passed without actual inference or sending mail.")
                return
            if args.suite.startswith("saved-analysis-"):
                from test_analysis_selection import (
                    test_current_precedes_newer_obsolete_success_then_falls_back_truthfully,
                    test_old_current_report_survives_large_retry_history_with_one_body,
                    test_report_scope_is_explicit_even_in_privileged_session,
                    test_selection_excludes_newer_attempt_and_rechecks_revoked_record,
                )
                case = args.suite.removeprefix("saved-analysis-")
                if case == "current":
                    test_old_current_report_survives_large_retry_history_with_one_body(harness)
                elif case == "fallback":
                    test_current_precedes_newer_obsolete_success_then_falls_back_truthfully(harness)
                elif case == "boundary":
                    test_selection_excludes_newer_attempt_and_rechecks_revoked_record(harness)
                else:
                    test_report_scope_is_explicit_even_in_privileged_session(harness, case)
                print("PostgreSQL:", args.suite, "passed; synthetic reports only.")
                return
            if args.suite.startswith("law-history-"):
                from test_law_history_metadata import (
                    test_law_detail_large_history_is_metadata_compatible_without_historical_body_loads,
                    test_law_history_keeps_scope_in_privileged_sessions,
                    test_saved_page_statistics_and_unicode_match_existing_metadata,
                )
                if args.suite == "law-history-large":
                    test_law_detail_large_history_is_metadata_compatible_without_historical_body_loads(harness)
                elif args.suite == "law-history-scope":
                    test_law_history_keeps_scope_in_privileged_sessions(harness)
                else:
                    pages, expected = {
                        "law-history-empty": ([], 0), "law-history-null": ([None, 0, None], 0),
                        "law-history-int": ([2, None, 12, 3], 12), "law-history-fraction": ([1, 2.5], 2.5),
                    }[args.suite]
                    test_saved_page_statistics_and_unicode_match_existing_metadata(harness, pages, expected)
                print("PostgreSQL:", args.suite, "passed; exact metadata and scoped history without model/mail calls.")
                return
            if args.suite.startswith("timeline-"):
                from test_registry_timeline_projections import (
                    test_large_metadata_pages_and_detail_remain_complete,
                    test_large_timeline_preserves_all_entries_without_hydrating_saved_bodies,
                    test_page_cursor_contract_and_access_are_rechecked,
                    test_timeline_cutoff_ties_deletion_and_late_backdated_detection,
                    test_timeline_header_explicit_scope_and_legacy_fallback,
                    test_timeline_private_history_and_observation_scope,
                    test_timeline_relation_fanout_uses_one_scoped_alias_query,
                )
                if args.suite == "timeline-large":
                    test_large_timeline_preserves_all_entries_without_hydrating_saved_bodies(harness)
                elif args.suite == "timeline-relations":
                    test_timeline_relation_fanout_uses_one_scoped_alias_query(harness)
                elif args.suite == "timeline-private":
                    test_timeline_private_history_and_observation_scope(harness)
                elif args.suite == "timeline-metadata":
                    test_large_metadata_pages_and_detail_remain_complete(harness)
                elif args.suite == "timeline-cursor":
                    test_page_cursor_contract_and_access_are_rechecked(harness)
                elif args.suite == "timeline-cutoff":
                    with MonkeyPatch.context() as patch:
                        test_timeline_cutoff_ties_deletion_and_late_backdated_detection(harness, patch)
                else:
                    test_timeline_header_explicit_scope_and_legacy_fallback(harness, args.suite.removeprefix("timeline-"))
                print("PostgreSQL:", args.suite, "passed; scalar timeline reads without provider/mail calls.")
                return
            if args.suite.startswith("relation-endpoints-"):
                from test_relation_endpoints import (
                    test_incoming_replacement_uses_official_subject_as_successor,
                    test_mismatched_pair_is_not_official_in_inbox_prompt_or_successor_action,
                    test_prepared_digest_cannot_derive_urgency_from_unrelated_replacement,
                )
                if args.suite.endswith("source") or args.suite.endswith("target"):
                    side = "subject_work_id" if args.suite.endswith("source") else "object_work_id"
                    test_mismatched_pair_is_not_official_in_inbox_prompt_or_successor_action(harness, side)
                elif args.suite.endswith("reverse"):
                    test_incoming_replacement_uses_official_subject_as_successor(harness)
                else:
                    with MonkeyPatch.context() as patch:
                        test_prepared_digest_cannot_derive_urgency_from_unrelated_replacement(harness, patch)
                print("PostgreSQL:", args.suite, "passed without real provider/mail calls.")
                return
            if args.suite.startswith("official-relation-"):
                from test_relation_official_freshness import (
                    test_corrected_official_fields_make_saved_report_history_only,
                    test_correction_changes_request_identity_and_failed_retry_never_revives_old,
                    test_digest_final_read_rechecks_corrected_relation_without_sending,
                    test_new_official_relation_invalidates_previously_unlinked_report,
                )
                if args.suite == "official-relation-fields":
                    test_corrected_official_fields_make_saved_report_history_only(harness, "state", "rejected")
                elif args.suite == "official-relation-links":
                    test_new_official_relation_invalidates_previously_unlinked_report(harness)
                elif args.suite == "official-relation-retry":
                    test_correction_changes_request_identity_and_failed_retry_never_revives_old(harness)
                else:
                    with MonkeyPatch.context() as patch:
                        test_digest_final_read_rechecks_corrected_relation_without_sending(harness, patch)
                print("PostgreSQL:", args.suite, "passed without real provider/mail calls.")
                return
            if args.suite.startswith("monitored-"):
                from test_registry_monitored_pages import (
                    test_monitored_comparison_links_choose_latest_visible_scalar_id,
                    test_monitored_current_user_read_state_ignores_older_event_and_foreign_principal,
                    test_monitored_dates_use_zurich_and_creation_fallback,
                    test_monitored_keysets_batch_details_without_hydrating_saved_bodies,
                    test_monitored_latest_event_index_roundtrip_preserves_events,
                    test_monitored_privileged_scope_never_borrows_foreign_law_mapping_or_work,
                    test_monitored_sparse_literal_search_and_legacy_defaults,
                )
                checks = {
                    "monitored-pages": test_monitored_keysets_batch_details_without_hydrating_saved_bodies,
                    "monitored-read": test_monitored_current_user_read_state_ignores_older_event_and_foreign_principal,
                    "monitored-scope": test_monitored_privileged_scope_never_borrows_foreign_law_mapping_or_work,
                    "monitored-dates": test_monitored_dates_use_zurich_and_creation_fallback,
                    "monitored-comparison": test_monitored_comparison_links_choose_latest_visible_scalar_id,
                    "monitored-migration": test_monitored_latest_event_index_roundtrip_preserves_events,
                }
                if args.suite == "monitored-search":
                    with MonkeyPatch.context() as patch:
                        test_monitored_sparse_literal_search_and_legacy_defaults(harness, patch)
                else:
                    checks[args.suite](harness)
                print("PostgreSQL:", args.suite, "passed without model calls.")
                return
            if args.suite in {"registry-details", "registry-detail-scope", "registry-detail-dates"}:
                from test_registry_detail_batches import (
                    test_empty_event_details_do_not_query_and_shared_work_dates_remain_event_specific,
                    test_event_detail_links_keep_explicit_scope_in_privileged_session,
                    test_event_detail_query_count_is_constant_and_scalar_for_one_and_fifty,
                )
                checks = {
                    "registry-details": test_event_detail_query_count_is_constant_and_scalar_for_one_and_fifty,
                    "registry-detail-scope": test_event_detail_links_keep_explicit_scope_in_privileged_session,
                    "registry-detail-dates": test_empty_event_details_do_not_query_and_shared_work_dates_remain_event_specific,
                }
                checks[args.suite](harness)
                print("PostgreSQL:", args.suite, "passed without model calls.")
                return
            if args.suite.startswith("registry-"):
                from test_registry_event_pages import (
                    test_equal_time_registry_pages_do_not_hydrate_event_or_work_payloads,
                    test_event_sql_bounds_zurich_dates_and_preserves_selected_date_metadata,
                    test_privileged_event_page_still_scopes_work_visibility_and_personal_read_state,
                    test_registry_keyset_index_migration_preserves_populated_events,
                    test_related_watch_filter_agrees_with_details_and_excludes_foreign_watches,
                    test_sparse_unicode_search_crosses_batches_and_only_expands_visible_details,
                )
                checks = {
                    "registry-watches": test_related_watch_filter_agrees_with_details_and_excludes_foreign_watches,
                    "registry-events": test_equal_time_registry_pages_do_not_hydrate_event_or_work_payloads,
                    "registry-dates": test_event_sql_bounds_zurich_dates_and_preserves_selected_date_metadata,
                    "registry-scope": test_privileged_event_page_still_scopes_work_visibility_and_personal_read_state,
                    "registry-migration": test_registry_keyset_index_migration_preserves_populated_events,
                }
                if args.suite == "registry-search":
                    with MonkeyPatch.context() as patch:
                        test_sparse_unicode_search_crosses_batches_and_only_expands_visible_details(harness, patch)
                else:
                    checks[args.suite](harness)
                print("PostgreSQL:", args.suite, "passed without event/work JSON hydration or model calls.")
                return
            if args.suite.startswith("evidence-pages") or args.suite == "evidence-text-pages":
                from test_evidence_pages import (
                    test_large_evidence_exact_target_and_sql_pages_without_full_orm_load,
                    test_plain_text_pages_preserve_every_character_and_empty_state,
                )
                if args.suite == "evidence-text-pages":
                    test_plain_text_pages_preserve_every_character_and_empty_state(harness, True)
                else:
                    test_large_evidence_exact_target_and_sql_pages_without_full_orm_load(harness, args.suite.endswith("native"))
                print("PostgreSQL:", args.suite, "passed with bounded transfer and no full ORM body loads.")
                return
            if args.suite.startswith("source-review"):
                from test_source_review import (
                    test_privileged_snapshot_does_not_borrow_foreign_subscription,
                    test_review_is_personal_passive_until_explicit_and_does_not_activate,
                    test_source_review_migration_preserves_prior_personal_data,
                )
                {"source-review": test_review_is_personal_passive_until_explicit_and_does_not_activate,
                 "source-review-scope": test_privileged_snapshot_does_not_borrow_foreign_subscription,
                 "source-review-migration": test_source_review_migration_preserves_prior_personal_data}[args.suite](harness)
                print("PostgreSQL:", args.suite, "passed without source activation or external calls.")
                return
            if args.suite.startswith("milestone-"):
                from test_onboarding_milestones import (
                    test_migration_preserves_personal_intent_and_existing_topic,
                    test_postgres_concurrent_first_steps_are_retained_once,
                    test_view_reads_are_passive_and_explicit_display_is_idempotent,
                )
                if args.suite == "milestone-native":
                    test_view_reads_are_passive_and_explicit_display_is_idempotent(harness, True)
                elif args.suite == "milestone-migration":
                    test_migration_preserves_personal_intent_and_existing_topic(harness)
                else:
                    test_postgres_concurrent_first_steps_are_retained_once(harness)
                print("PostgreSQL:", args.suite, "passed without live sources, model or mail.")
                return
            if args.suite.startswith("feed-readiness-"):
                from test_feed_readiness import (
                    test_history_only_reports_current_revision_and_checkpoint,
                    test_readiness_bounds_topics_and_isolates_even_privileged_sessions,
                    test_readiness_is_passive_and_source_failure_does_not_become_quiet,
                )
                if args.suite == "feed-readiness-history":
                    test_history_only_reports_current_revision_and_checkpoint(harness, "complete", "complete")
                elif args.suite == "feed-readiness-bounds":
                    test_readiness_bounds_topics_and_isolates_even_privileged_sessions(harness)
                else:
                    test_readiness_is_passive_and_source_failure_does_not_become_quiet(harness)
                print("PostgreSQL:", args.suite, "passes with saved scalar state and no live calls.")
                return
            if args.suite.startswith("onboarding-"):
                from test_personal_onboarding import (
                    test_defer_resume_idempotence_and_principal_isolation,
                    test_onboarding_migration_preserves_existing_watch,
                    test_postgres_first_use_from_two_tabs_is_one_personal_record,
                )
                {"onboarding-state": test_defer_resume_idempotence_and_principal_isolation,
                 "onboarding-migration": test_onboarding_migration_preserves_existing_watch,
                 "onboarding-race": test_postgres_first_use_from_two_tabs_is_one_personal_record}[args.suite](harness)
                print("PostgreSQL personal onboarding:", args.suite, "passed; no real source, model or email calls.")
                return
            if args.suite == "assistant-context":
                test_personal_message_context_reads_selected_user_text_without_sharing_or_inference(harness)
                print("PostgreSQL: selected personal message context preserves privacy without monitoring writes or inference.")
                return
            if args.suite == "assistant-context-private":
                test_personal_context_fails_closed_for_wrong_owner_role_or_unavailable_message(harness, "other_user")
                print("PostgreSQL: another principal cannot read the personal message even in a privileged organization session.")
                return
            if args.suite == "answer-context":
                test_saved_answer_context_keeps_question_and_comparison_without_new_inference_or_writes(harness)
                print("PostgreSQL: saved cited answer context preserves question and comparison without extra inference or writes.")
                return
            if args.suite == "answer-context-private":
                test_answer_context_checks_all_owners_even_in_privileged_session(harness, "version")
                print("PostgreSQL: a private saved version prevents contextual disclosure even in a privileged session.")
                return
            if args.suite.startswith("topic-coverage"):
                check = {"topic-coverage-empty": test_unscheduled_unsubscribed_preview_remains_read_only_without_inference,
                         "topic-coverage-state": test_custom_schedule_partial_health_and_old_success_are_separate_saved_facts,
                         "topic-coverage-scope": test_privileged_preview_does_not_borrow_other_organization_subscription,
                         "topic-coverage-bounds": test_one_and_all_packs_use_four_scalar_queries_without_diagnostic_hydration}[args.suite]
                check(harness)
                print("PostgreSQL: saved topic source readiness, no-write preview, owner scope or scalar bounds passed.")
                return
            if args.suite.startswith("topic-duplicates"):
                check = {"topic-duplicates": test_rule_warning_is_read_only_case_order_insensitive_and_excludes_self,
                         "topic-duplicates-scope": test_privileged_query_still_checks_both_topic_and_revision_owners,
                         "topic-duplicates-bounds": test_warning_reads_at_most_501_current_scalar_rules_and_discloses_both_limits}[args.suite]
                check(harness)
                print("PostgreSQL: topic duplicate warning contract, owner scope or scalar bounds passed without inference.")
                return
            if args.suite == "monitoring-context":
                test_native_event_context_uses_saved_title_and_artifact_without_automatic_monitoring(harness)
                print("PostgreSQL: native context lookup remains read-only, scalar and exact without creating monitoring.")
                return
            if args.suite == "monitoring-context-activate":
                test_context_to_topic_preview_and_explicit_activation_reuses_existing_lifecycle(harness)
                print("PostgreSQL: contextual topic preview stays read-only; explicit activation and repeated confirmation create one topic.")
                return
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
            if args.suite.startswith("digest-quiet-"):
                import pytest
                from test_digest_quiet import (
                    test_deferred_job_resumes_once_or_honors_unsubscribe,
                    test_quiet_boundary_is_rechecked_after_render,
                    test_quiet_save_preserves_due_and_old_client_fields,
                )
                with pytest.MonkeyPatch.context() as patch:
                    if args.suite == "digest-quiet-save":
                        test_quiet_save_preserves_due_and_old_client_fields(harness)
                    elif args.suite == "digest-quiet-boundary":
                        test_quiet_boundary_is_rechecked_after_render(harness, patch)
                    else:
                        test_deferred_job_resumes_once_or_honors_unsubscribe(harness, patch, args.suite.endswith("unsubscribe"))
                print("PostgreSQL:", args.suite, "passes; all mail intercepted.")
                return
            if args.suite == "digest-local-schedule":
                test_local_schedule_save_retry_legacy_omission_and_clear(harness)
                print("PostgreSQL: local digest schedule save/retry/legacy omission/clear remain stable.")
                return
            if args.suite == "digest-schedule-migration":
                test_schedule_migration_preserves_existing_preferences(harness)
                print("PostgreSQL: optional schedule migration preserves existing digest preferences and due time.")
                return
            if args.suite == "feed-topic-sparse":
                test_sparse_topic_batches_never_hide_later_valid_matches(harness)
                print("PostgreSQL: topic paging traverses 120 stale candidates and excludes rejected/currently invalid matches.")
                return
            if args.suite == "feed-topic-scope":
                test_topic_page_scope_revocation_and_cursor_kind(harness)
                print("PostgreSQL: topic pages bind principal/event/type and recheck revoked admission.")
                return
            if args.suite == "feed-watch-pages":
                test_large_watch_fanout_is_complete_bounded_and_does_not_hydrate_laws(harness)
                print("PostgreSQL: 1001 direct watches traverse bounded pages without hydrating full laws or inference.")
                return
            if args.suite == "feed-watch-scope":
                test_watch_cursor_rechecks_visibility_and_excludes_late_watches(harness)
                print("PostgreSQL: watch cursor visibility, late additions and principal scope checked.")
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
