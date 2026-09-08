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
from test_interest_admission import (
    test_65_current_interests_fail_as_a_whole_not_a_sample,
    test_changed_inputs_reject_fenced_inflight_completion,
    test_foreign_worker_cannot_assemble_even_with_privileged_session,
    test_full_traversal_continues_beyond_100_stale_candidates,
    test_law_admission_excludes_inactive_or_foreign_evidence,
    test_law_and_direct_watch_inputs_use_exact_legacy_evidence,
    test_prepare_generate_finish_reuses_exact_brief_and_rechecks_inputs,
    test_reused_session_reloads_external_edits_and_excludes_other_profiles,
)
from test_interest_assessment_store import (
    test_concurrent_reservations_and_claims_produce_one_assessment_and_one_owner,
    test_cross_org_reads_and_writes_are_rejected_even_in_privileged_session,
    test_migration_roundtrip_preserves_existing_corpus_and_matches,
    test_persisted_brief_is_reused_without_inference_and_preserves_exact_source_bindings,
    test_retry_is_explicit_bounded_and_does_not_store_provider_secrets,
    test_revised_input_supersedes_inflight_work_and_old_worker_cannot_publish,
    test_unverified_result_cannot_be_persisted,
)
from test_interest_automation import (
    test_admission_lease_and_policy_checked_after_measurement,
    test_backfill_admits_every_batch_atomically_without_ai,
    test_crash_after_admission_reuses_job_before_advancing_cursor,
    test_duplicate_delivery_coalesces_measured_admission,
    test_limited_event_is_audited_then_later_event_admitted,
    test_matching_outbox_admission_generation_and_reader,
)
from test_interest_brief_reader import (
    test_changed_current_binding_never_displays_saved_answer_as_current,
    test_corrupted_saved_output_or_proof_is_not_displayed,
    test_exact_shared_result_reuses_without_generation_or_jobs,
    test_revoked_admission_denies_saved_answer_before_runtime_probe,
)
from test_interest_execution import (
    artifacts as execution_artifacts,
)
from test_interest_execution import (
    execution as execution_fixture,
)
from test_interest_execution import (
    test_changed_saved_input_cannot_publish,
    test_database_connections_not_held_during_provider_calls,
    test_interruption_closes_attempt_and_restores_context,
    test_measured_complete_request_persisted_and_exact_reuse,
    test_single_repair_shared_budget_and_failure_is_not_retried_on_read,
)
from test_interest_jobs import (
    test_changed_admission_cancels_stale_job_without_losing_history,
    test_concurrent_admission_has_one_job_and_one_outbox,
    test_crashed_lease_recovers_assessment_and_fences_old_token,
    test_dispatch_does_not_steal_running_lease_or_bypass_backoff,
    test_exhausted_crash_recovery_closes_unfinished_assessment,
    test_lost_lease_cannot_finish_new_workers_job,
    test_postgres_dispatch_skips_locked_job_without_locking_its_outbox,
    test_schedule_outbox_execute_service_and_exact_reuse,
    test_separate_connections_coalesce_simultaneous_admission,
)
from test_interest_material import (
    test_conflicting_baselines_require_selection_not_import_time_guess,
    test_material_plan_is_measured_and_generated_once_by_real_local_gateway,
    test_old_comparison_mode_does_not_hide_complete_saved_pair,
    test_saved_comparison_reaches_current_admission_generation_and_fenced_storage,
    test_stale_comparison_during_generation_supersedes_without_publishing,
)
from test_interest_policy import (
    test_api_bounds_conflict_noop_and_saved_persistence,
    test_concurrent_policy_editors_cannot_overwrite_each_other,
    test_disable_cancels_automatic_work_without_publishing,
    test_language_variants_do_not_supersede_each_other,
    test_lower_saved_allowance_applies_to_new_admission_and_rolls_back,
    test_matching_schedules_distinct_active_user_languages_not_admin_fallback,
    test_policy_migration_preserves_existing_organization,
)
from test_native_comparison_views import (
    test_candidates_paginate_without_private_or_other_language_versions,
    test_http_save_complete_pair_page_exact_changes_and_clear,
    test_oversized_ai_dossier_still_has_complete_paged_comparison,
    test_stale_comparison_returns_recoverable_state_without_old_passages,
)
from test_native_comparisons import (
    test_baseline_changes_and_clear_preserve_history_and_revision_tombstone,
    test_complete_large_native_pair_persists_and_reuses_without_import_order_guess,
    test_concurrent_editors_cannot_overwrite_each_other,
    test_local_runner_uses_native_pair_once_and_persists_exact_comparison,
    test_native_migration_roundtrip_preserves_saved_corpus,
    test_native_selection_change_during_generation_cannot_publish,
    test_selection_does_not_commit_callers_transaction,
    test_tenant_selection_never_leaks_into_another_admitted_organization,
)


def execute_local(harness, scenario):
    from pytest import MonkeyPatch
    with TemporaryDirectory(prefix="helvetic-synthetic-approval-") as directory, MonkeyPatch.context() as patch:
        artifacts = execution_artifacts.__wrapped__(Path(directory))
        execution = execution_fixture.__wrapped__(harness, artifacts, patch)
        scenario(execution)

SUITES = {
    "policy-languages": test_matching_schedules_distinct_active_user_languages_not_admin_fallback,
    "policy-variants": test_language_variants_do_not_supersede_each_other,
    "policy-persistence": test_api_bounds_conflict_noop_and_saved_persistence,
    "policy-concurrency": test_concurrent_policy_editors_cannot_overwrite_each_other,
    "policy-cancel": lambda harness: execute_local(harness, lambda value: test_disable_cancels_automatic_work_without_publishing(value, "generate")),
    "policy-quota": lambda harness: execute_local(harness, lambda value: test_lower_saved_allowance_applies_to_new_admission_and_rolls_back(value, "max_pending")),
    "policy-migration": test_policy_migration_preserves_existing_organization,
    "auto-roundtrip": lambda harness: execute_local(harness, test_matching_outbox_admission_generation_and_reader),
    "auto-backfill": test_backfill_admits_every_batch_atomically_without_ai,
    "auto-limit": lambda harness: execute_local(harness, test_limited_event_is_audited_then_later_event_admitted),
    "auto-recovery": lambda harness: execute_local(harness, test_crash_after_admission_reuses_job_before_advancing_cursor),
    "auto-lease": lambda harness: execute_local(harness, lambda value: test_admission_lease_and_policy_checked_after_measurement(value, "same_owner")),
    "auto-duplicate": lambda harness: execute_local(harness, test_duplicate_delivery_coalesces_measured_admission),
    "reader-current": lambda harness: execute_local(harness, test_exact_shared_result_reuses_without_generation_or_jobs),
    "reader-stale": lambda harness: execute_local(harness, lambda value: test_changed_current_binding_never_displays_saved_answer_as_current(value, "profile")),
    "reader-invalid": lambda harness: execute_local(harness, lambda value: test_corrupted_saved_output_or_proof_is_not_displayed(value, "citation")),
    "reader-revoked": lambda harness: execute_local(harness, test_revoked_admission_denies_saved_answer_before_runtime_probe),
    "jobs-exhausted": lambda harness: execute_local(harness, test_exhausted_crash_recovery_closes_unfinished_assessment),
    "jobs-threaded": lambda harness: execute_local(harness, test_separate_connections_coalesce_simultaneous_admission),
    "jobs-dispatch-lock": lambda harness: execute_local(harness, test_postgres_dispatch_skips_locked_job_without_locking_its_outbox),
    "jobs-roundtrip": lambda harness: execute_local(harness, test_schedule_outbox_execute_service_and_exact_reuse),
    "jobs-recovery": lambda harness: execute_local(harness, test_crashed_lease_recovers_assessment_and_fences_old_token),
    "jobs-dispatch": lambda harness: execute_local(harness, test_dispatch_does_not_steal_running_lease_or_bypass_backoff),
    "jobs-lease": lambda harness: execute_local(harness, lambda value: test_lost_lease_cannot_finish_new_workers_job(value, True)),
    "jobs-supersession": lambda harness: execute_local(harness, test_changed_admission_cancels_stale_job_without_losing_history),
    "jobs-concurrency": lambda harness: execute_local(harness, test_concurrent_admission_has_one_job_and_one_outbox),
    "native-ui-roundtrip": test_http_save_complete_pair_page_exact_changes_and_clear,
    "native-ui-large": test_oversized_ai_dossier_still_has_complete_paged_comparison,
    "native-ui-candidates": test_candidates_paginate_without_private_or_other_language_versions,
    "native-ui-revocation": lambda harness: test_stale_comparison_returns_recoverable_state_without_old_passages(harness, "grant"),
    "native-complete": test_complete_large_native_pair_persists_and_reuses_without_import_order_guess,
    "native-selection": test_baseline_changes_and_clear_preserve_history_and_revision_tombstone,
    "native-rollback": test_selection_does_not_commit_callers_transaction,
    "native-concurrency": test_concurrent_editors_cannot_overwrite_each_other,
    "native-migration": test_native_migration_roundtrip_preserves_saved_corpus,
    "native-scope": test_tenant_selection_never_leaks_into_another_admitted_organization,
    "native-gateway": lambda harness: execute_local(harness, test_local_runner_uses_native_pair_once_and_persists_exact_comparison),
    "native-fence": lambda harness: execute_local(harness, test_native_selection_change_during_generation_cannot_publish),
    "material-reuse": test_saved_comparison_reaches_current_admission_generation_and_fenced_storage,
    "material-fence": test_stale_comparison_during_generation_supersedes_without_publishing,
    "material-baseline": test_conflicting_baselines_require_selection_not_import_time_guess,
    "material-existing-mode": test_old_comparison_mode_does_not_hide_complete_saved_pair,
    "material-gateway": lambda harness: execute_local(harness, lambda value: test_material_plan_is_measured_and_generated_once_by_real_local_gateway(value, harness)),
    "execution-reuse": lambda harness: execute_local(harness, test_measured_complete_request_persisted_and_exact_reuse),
    "execution-transactions": lambda harness: execute_local(harness, test_database_connections_not_held_during_provider_calls),
    "execution-fence": lambda harness: execute_local(harness, lambda value: test_changed_saved_input_cannot_publish(value, "generate")),
    "execution-repair": lambda harness: execute_local(harness, lambda value: test_single_repair_shared_budget_and_failure_is_not_retried_on_read(value, 1)),
    "execution-cancel": lambda harness: execute_local(harness, lambda value: test_interruption_closes_attempt_and_restores_context(value, "cancelled")),
    "current-reuse": test_prepare_generate_finish_reuses_exact_brief_and_rechecks_inputs,
    "current-law-watch": test_law_and_direct_watch_inputs_use_exact_legacy_evidence,
    "current-scope": test_foreign_worker_cannot_assemble_even_with_privileged_session,
    "current-sparse": test_full_traversal_continues_beyond_100_stale_candidates,
    "current-overflow": test_65_current_interests_fail_as_a_whole_not_a_sample,
    "current-refresh": test_reused_session_reloads_external_edits_and_excludes_other_profiles,
    "current-fence": lambda harness: test_changed_inputs_reject_fenced_inflight_completion(harness, "new_interest"),
    "current-rescore": lambda harness: test_law_admission_excludes_inactive_or_foreign_evidence(harness, "withdrawn_signals"),
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
