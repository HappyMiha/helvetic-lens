"""Matrix reads retain complete report eligibility without transferring archives."""

from datetime import timedelta

import pytest
from sqlalchemy import event, insert, select, update
from sqlalchemy.orm import Session
from test_analysis_selection import seed

from helvetic_lens import analysis as ai
from helvetic_lens.db import utcnow
from helvetic_lens.impact_matrix import ImpactMatrixReader
from helvetic_lens.models import Analysis, Comparison, DocumentWatch, Law, Organization, Profile, Version


def reader(service):
    return ImpactMatrixReader(
        organization_id=service.organization_id,
        profile_id=service.tenant_record_id,
        settings=service.settings,
        prompts=service.prompt_settings,
        output_locale="en-CH",
        runtime_identity=service.cache_runtime_identity(),
    )


def observe(harness):
    client, _, service, _ = harness
    loaded, queries = [], []

    def load(_session, value):
        if isinstance(value, (Analysis, Comparison)):
            loaded.append((type(value).__name__, value.id))

    def sql(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().startswith("SELECT"):
            queries.append(statement)

    event.listen(Session, "loaded_as_persistent", load)
    event.listen(service.db.engine, "before_cursor_execute", sql)
    try:
        response = client.get("/api/impact-matrix", params={"output_locale": "en-CH"})
        assert response.status_code == 200, response.text
    finally:
        event.remove(Session, "loaded_as_persistent", load)
        event.remove(service.db.engine, "before_cursor_execute", sql)
    return response.json(), loaded, queries


def test_matrix_large_history_loads_only_selected_comparison_and_result(harness):
    _, _, service, model = harness
    law, comparison, current, calls = seed(harness)
    with service.db.session() as session:
        selected = session.get(Comparison, comparison["id"])
        session.execute(
            insert(Comparison),
            [
                dict(
                    id=f"88000000-0000-0000-0000-{i:012}",
                    law_id=law["id"],
                    owner_organization_id=service.organization_id,
                    old_version_id=selected.old_version_id,
                    new_version_id=selected.new_version_id,
                    mode=f"archive-{i}",
                    diff={"archive": "large diff " * 2000},
                    created_at=selected.created_at - timedelta(days=1),
                )
                for i in range(151)
            ],
        )
        session.commit()
    result, loaded, queries = observe(harness)
    row = result["rows"][0]
    assert row["analysis_id"] == current["id"]
    assert row["report_state"] == "current" and row["latest_attempt_status"] == "failed"
    assert loaded == [("Comparison", comparison["id"])]
    assert len(queries) == 9  # Includes three request configuration reads.
    assert not any("analyses.analysis_plan" in query or "analyses.provenance" in query for query in queries)
    assert len(model.calls) == calls


def test_matrix_invalid_json_results_do_not_displace_saved_object(harness):
    _, _, service, model = harness
    _, comparison, current, calls = seed(harness, 5)
    with service.db.session() as session:
        attempts = list(
            session.scalars(select(Analysis).where(Analysis.id != current["id"]).order_by(Analysis.id))
        )
        for attempt, invalid in zip(attempts, [None, [], "text", 7, True], strict=True):
            attempt.status = "succeeded"
            attempt.cache_key = current["cache_key"]
            attempt.result = invalid
        session.commit()
    matrix, _, _ = observe(harness)
    assert matrix["rows"][0]["analysis_id"] == current["id"]
    with service.db.session() as session:
        session.get(Analysis, current["id"]).cache_key = "obsolete"
        session.commit()
    matrix, _, _ = observe(harness)
    assert matrix["rows"][0]["report_state"] == "stale"
    with service.db.session() as session:
        session.get(Analysis, current["id"]).result = None
        session.commit()
    matrix, _, _ = observe(harness)
    assert matrix["rows"][0]["report_state"] == "unanalysed"
    assert matrix["rows"][0]["analysis_id"] is None
    assert len(model.calls) == calls


@pytest.mark.parametrize("hidden", ["watch", "law", "comparison", "analysis", "profile"])
def test_matrix_explicit_scope_in_privileged_session(harness, hidden):
    _, _, service, _ = harness
    law, comparison, current, _ = seed(harness, 1)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Other matrix", slug="other-matrix")
        session.add(foreign)
        session.flush()
        if hidden == "watch":
            session.scalar(
                select(DocumentWatch).where(DocumentWatch.law_id == law["id"])
            ).organization_id = foreign.id
        elif hidden == "profile":
            session.get(Profile, service.tenant_record_id).organization_id = foreign.id
        elif hidden == "analysis":
            for attempt in session.scalars(
                select(Analysis).where(Analysis.comparison_id == comparison["id"])
            ):
                attempt.organization_id = foreign.id
        elif hidden == "comparison":
            session.get(Comparison, comparison["id"]).owner_organization_id = foreign.id
        else:
            session.get(Law, law["id"]).owner_organization_id = foreign.id
        session.commit()
        result = reader(service).page(session)
        if hidden in {"watch", "law", "profile"}:
            assert result["rows"] == []
        else:
            row = result["rows"][0]
            assert row["analysis_id"] is None and row["report_state"] == "unanalysed"
            if hidden == "comparison":
                assert row["comparison_id"] is None


def test_matrix_batches_51_documents_without_per_document_history_queries(harness):
    _, _, service, model = harness
    law, comparison, current, calls = seed(harness, 1)
    stamp = utcnow()
    with service.db.session() as session:
        original = session.get(Comparison, comparison["id"])
        profile = session.get(Profile, service.tenant_record_id)
        for i in range(50):
            new_law = Law(
                name=f"Matrix {i}",
                url=f"https://matrix.example/{i}",
                owner_organization_id=service.organization_id,
            )
            session.add(new_law)
            session.flush()
            version_ids = []
            for source_id in (original.old_version_id, original.new_version_id):
                version = session.get(Version, source_id)
                values = {
                    col.name: getattr(version, col.name)
                    for col in Version.__table__.columns
                    if col.name not in {"id", "law_id"}
                }
                copy = Version(law_id=new_law.id, **values)
                session.add(copy)
                session.flush()
                version_ids.append(copy.id)
            cmp = Comparison(
                law_id=new_law.id,
                owner_organization_id=service.organization_id,
                old_version_id=version_ids[0],
                new_version_id=version_ids[1],
                mode="manual",
                diff=original.diff,
                identity_json=original.identity_json,
                created_at=stamp,
            )
            session.add(cmp)
            session.flush()
            session.add(
                DocumentWatch(
                    organization_id=service.organization_id,
                    law_id=new_law.id,
                    display_name=new_law.name,
                    active=True,
                )
            )
            key = ai.cache_key(
                cmp,
                profile,
                service.settings,
                service.prompt_settings,
                "en-CH",
                runtime_identity=service.cache_runtime_identity(),
            )
            session.add(
                Analysis(
                    organization_id=service.organization_id,
                    comparison_id=cmp.id,
                    cache_key=key,
                    status="succeeded",
                    result=current["result"],
                    model="synthetic",
                    created_at=stamp,
                )
            )
        session.commit()
    matrix, loaded, queries = observe(harness)
    assert matrix["summary"]["documents"] == matrix["summary"]["current_reports"] == 51
    assert len(loaded) == 51 and all(kind == "Comparison" for kind, _ in loaded)
    assert len(queries) == 13  # Second 50-law batch adds four reads.
    assert len(model.calls) == calls


def test_matrix_latest_comparison_tie_does_not_borrow_older_report(harness):
    _, _, service, model = harness
    law, comparison, _, calls = seed(harness, 1)
    with service.db.session() as session:
        previous = session.get(Comparison, comparison["id"])
        latest = Comparison(
            id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            law_id=law["id"],
            owner_organization_id=service.organization_id,
            old_version_id=previous.old_version_id,
            new_version_id=previous.new_version_id,
            mode="newest-tie",
            diff=previous.diff,
            created_at=previous.created_at,
        )
        session.add(latest)
        session.commit()
    matrix, loaded, _ = observe(harness)
    row = matrix["rows"][0]
    assert row["comparison_id"] == latest.id and row["report_state"] == "unanalysed"
    assert row["analysis_id"] is None
    assert loaded == [("Comparison", latest.id)]
    assert len(model.calls) == calls


def test_matrix_rechecks_cache_key_when_loading_selected_result(harness):
    _, _, service, _ = harness
    _, _, current, _ = seed(harness, 1)
    changed = []

    def correct(conn, _cursor, statement, _params, _context, _many):
        if not changed and statement.startswith("SELECT analyses.id, analyses.cache_key,"):
            changed.append(True)
            conn.execute(
                update(Analysis.__table__)
                .where(
                    Analysis.__table__.c.id == current["id"],
                )
                .values(cache_key="corrected-between-selection-and-load")
            )

    event.listen(service.db.engine, "before_cursor_execute", correct)
    try:
        matrix, _, _ = observe(harness)
    finally:
        event.remove(service.db.engine, "before_cursor_execute", correct)
    assert changed
    assert matrix["rows"][0]["analysis_id"] == current["id"]
    assert matrix["rows"][0]["report_state"] == "stale"
