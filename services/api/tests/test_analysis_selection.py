"""Old current reports remain visible after large retry histories, without inference."""

from datetime import timedelta

import pytest
from conftest import add_law
from sqlalchemy import event, insert, select
from sqlalchemy.orm import Session
from test_ai_history import saved_comparison

from helvetic_lens import analysis_selection
from helvetic_lens.db import utcnow
from helvetic_lens.models import Analysis, Comparison, Law, Organization


def seed(harness, count=1001):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    _, comparison = saved_comparison(client, law)
    response = client.post(f"/api/comparisons/{comparison['id']}/analyse")
    assert response.status_code == 200, response.text
    current = response.json()
    assert current["status"] == "succeeded"
    stamp = utcnow() - timedelta(days=2)
    with service.db.session() as session:
        session.get(Analysis, current["id"]).created_at = stamp - timedelta(days=1)
        session.execute(
            insert(Analysis),
            [
                dict(
                    id=f"99000000-0000-0000-0000-{i:012}",
                    organization_id=service.organization_id,
                    comparison_id=comparison["id"],
                    cache_key="0" * 64,
                    status="failed",
                    result=None,
                    model="synthetic",
                    error=f"Synthetic failure {i}",
                    analysis_plan={"large": "archived plan " * 1000},
                    created_at=stamp,
                )
                for i in range(count)
            ],
        )
        session.commit()
    return law, comparison, current, len(model.calls)


def test_old_current_report_survives_large_retry_history_with_one_body(harness):
    client, _, service, model = harness
    law, comparison, current, calls = seed(harness)
    loaded, queries = [], []

    def load(_session, value):
        if isinstance(value, Analysis):
            loaded.append(value.id)

    def sql(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().startswith("SELECT") and "FROM analyses" in statement:
            queries.append(statement)

    event.listen(Session, "loaded_as_persistent", load)
    event.listen(service.db.engine, "before_cursor_execute", sql)
    try:
        with service.db.session() as session:
            selected = service.latest_analysis(session, session.get(Comparison, comparison["id"]))
    finally:
        event.remove(Session, "loaded_as_persistent", load)
        event.remove(service.db.engine, "before_cursor_execute", sql)
    assert selected["id"] == current["id"] and selected["stale"] is False
    assert selected["latest_attempt"]["id"] == "99000000-0000-0000-0000-000000001000"
    assert selected["latest_attempt"]["created_at"].endswith("+00:00")
    assert len(queries) == 3 and loaded == [current["id"]]
    assert sum("analyses.analysis_plan" in query for query in queries) == 1
    assert all("LIMIT" in query for query in queries[:2])
    for url in (f"/api/comparisons/{comparison['id']}", f"/api/laws/{law['id']}?paged_history=true"):
        response = client.get(url)
        assert response.status_code == 200, response.text
        actual = response.json()["analysis"]
        assert actual["id"] == current["id"] and actual["stale"] is False
        assert actual["result"] == current["result"]
        assert actual["use_count"] == current["use_count"]
        assert actual["latest_attempt"]["error"] == "Synthetic failure 1000"
    assert len(model.calls) == calls


def test_current_precedes_newer_obsolete_success_then_falls_back_truthfully(harness):
    client, _, service, model = harness
    _, comparison, current, calls = seed(harness, 61)
    previous_id = "99000000-0000-0000-0000-000000000050"
    with service.db.session() as session:
        previous = session.get(Analysis, previous_id)
        previous.status = "succeeded"
        previous.result = current["result"]
        session.commit()
    url = f"/api/comparisons/{comparison['id']}"
    assert client.get(url).json()["analysis"]["id"] == current["id"]
    with service.db.session() as session:
        session.get(Analysis, current["id"]).cache_key = "1" * 64
        session.commit()
    result = client.get(url).json()["analysis"]
    assert result["id"] == previous_id and result["stale"] is True
    assert result["latest_attempt"]["status"] == "failed"
    with service.db.session() as session:
        session.get(Analysis, previous_id).status = "failed"
        session.get(Analysis, current["id"]).status = "failed"
        session.commit()
    result = client.get(url).json()["analysis"]
    assert result["id"] == "99000000-0000-0000-0000-000000000060"
    assert result["status"] == "failed" and "latest_attempt" not in result
    assert len(model.calls) == calls


@pytest.mark.parametrize("hidden", ["analysis", "comparison", "law"])
def test_report_scope_is_explicit_even_in_privileged_session(harness, hidden):
    _, _, service, _ = harness
    law, comparison, current, _ = seed(harness, 1)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign report", slug="foreign-report")
        session.add(foreign)
        session.flush()
        if hidden == "analysis":
            for row in session.scalars(select(Analysis).where(Analysis.comparison_id == comparison["id"])):
                row.organization_id = foreign.id
        else:
            row = session.get(
                Comparison if hidden == "comparison" else Law,
                comparison["id"] if hidden == "comparison" else law["id"],
            )
            row.owner_organization_id = foreign.id
        session.commit()
        assert service.latest_analysis(session, session.get(Comparison, comparison["id"])) is None


def test_selection_excludes_newer_attempt_and_rechecks_revoked_record(harness):
    _, _, service, _ = harness
    _, comparison, current, _ = seed(harness, 1)
    with service.db.session() as session:
        latest = analysis_selection.latest_attempt(session, service.organization_id, comparison["id"])
        session.add(
            Analysis(
                organization_id=service.organization_id,
                comparison_id=comparison["id"],
                cache_key=current["cache_key"],
                status="succeeded",
                result=current["result"],
                model="synthetic",
                created_at=utcnow(),
            )
        )
        session.commit()
        selected = analysis_selection.report(
            session, service.organization_id, comparison["id"], current["cache_key"], latest
        )
        assert selected.id == current["id"]
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Revoked report", slug="revoked-report")
        session.add(foreign)
        session.flush()
        session.get(Comparison, comparison["id"]).owner_organization_id = foreign.id
        session.commit()
        assert (
            analysis_selection.report(
                session, service.organization_id, comparison["id"], current["cache_key"], latest
            )
            is None
        )


def test_empty_history_does_not_probe_runtime_or_generate(harness, monkeypatch):
    client, _, service, model = harness
    law = add_law(client)
    _, comparison = saved_comparison(client, law)

    def unexpected_probe():
        raise AssertionError("Empty history must not probe the model runtime")

    monkeypatch.setattr(service, "cache_runtime_identity", unexpected_probe)
    with service.db.session() as session:
        assert service.latest_analysis(session, session.get(Comparison, comparison["id"])) is None
    assert model.calls == []


def test_foreign_current_success_cannot_displace_own_report(harness):
    _, _, service, _ = harness
    _, comparison, current, _ = seed(harness, 2)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Other organization", slug="foreign-current-report")
        session.add(foreign)
        session.flush()
        session.add(
            Analysis(
                organization_id=foreign.id,
                comparison_id=comparison["id"],
                cache_key=current["cache_key"],
                status="succeeded",
                result={"secret": "foreign conclusion"},
                error="Foreign diagnostic",
                model="synthetic",
                created_at=utcnow(),
            )
        )
        session.commit()
        selected = service.latest_analysis(session, session.get(Comparison, comparison["id"]))
        assert selected["id"] == current["id"]
        assert selected["latest_attempt"]["error"] == "Synthetic failure 1"
