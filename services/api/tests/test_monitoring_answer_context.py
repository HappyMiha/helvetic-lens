"""Only saved, supported cited answers can seed a reviewed monitoring draft."""
import pytest
from conftest import add_law
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from test_ai_history import saved_comparison

from helvetic_lens.config import DomainError
from helvetic_lens.models import AskRecord, Comparison, Job, Law, MonitoringTopic, Organization, Version
from helvetic_lens.monitoring_context import describe


def saved_answer(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    _, comparison = saved_comparison(client, law)
    response = client.post(f"/api/comparisons/{comparison['id']}/ask", json={"question": "What changed?", "history": []})
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["supported"] and answer["citations"]
    return law, comparison, answer["record_id"]


def test_saved_answer_context_keeps_question_and_comparison_without_new_inference_or_writes(harness):
    client, _, service, model = harness
    law, comparison, record_id = saved_answer(harness)
    calls = len(model.calls)
    with service.db.session() as session:
        before = [session.scalar(select(func.count()).select_from(table)) for table in (Job, MonitoringTopic, AskRecord)]
        uses = session.get(AskRecord, record_id).use_count
    loaded = []
    def track(session, instance):
        loaded.append(type(instance))
    event.listen(Session, "loaded_as_persistent", track)
    try:
        response = client.get("/api/monitoring-context", params={"kind": "answer", "id": record_id})
    finally:
        event.remove(Session, "loaded_as_persistent", track)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["question"] == "What changed?" and result["title"] == law["name"]
    assert result["comparison_id"] == comparison["id"] and result["answer_created_at"]
    assert result["reference_url"] == f"/compare/{comparison['id']}?task=ask"
    assert result["id"] == record_id and result["kind"] == "answer"
    assert result["ai_calls"] == 0 and result["requires_confirmation"] is True
    assert "result" not in result and "citations" not in result and "history" not in result
    assert not set(loaded) & {Law, Version, Comparison, AskRecord}
    with service.db.session() as session:
        assert before == [session.scalar(select(func.count()).select_from(table)) for table in (Job, MonitoringTopic, AskRecord)]
        assert session.get(AskRecord, record_id).use_count == uses
    assert len(model.calls) == calls


@pytest.mark.parametrize("condition", ["failed", "pending", "unsupported", "unsupported_string", "uncited", "malformed", "foreign_citation", "invalid_version_type"])
def test_unusable_saved_answer_is_not_a_monitoring_context(harness, condition):
    client, _, service, _ = harness
    _, _, record_id = saved_answer(harness)
    with service.db.session() as session:
        record = session.get(AskRecord, record_id)
        result = dict(record.result)
        if condition in {"failed", "pending"}:
            record.status = condition
        elif condition in {"unsupported", "unsupported_string"}:
            result["supported"] = "true" if condition == "unsupported_string" else False
        else:
            result["citations"] = {"uncited": [], "malformed": "citation text",
                "foreign_citation": [{"version_id": "foreign", "passage_id": "p1"}],
                "invalid_version_type": [{"version_id": [], "passage_id": "p1"}]}[condition]
        record.result = result
        session.commit()
    assert client.get("/api/monitoring-context", params={"kind": "answer", "id": record_id}).status_code == 404


@pytest.mark.parametrize("owner", ["answer", "comparison", "law", "version"])
def test_answer_context_checks_all_owners_even_in_privileged_session(harness, owner):
    client, _, service, _ = harness
    law, comparison, record_id = saved_answer(harness)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Private answer owner", slug="private-answer-owner")
        session.add(other)
        session.flush()
        if owner == "answer":
            session.get(AskRecord, record_id).organization_id = other.id
        else:
            table, entity_id = {"comparison": (Comparison, comparison["id"]), "law": (Law, law["id"]),
                                "version": (Version, law["current_version_id"])}[owner]
            session.get(table, entity_id).owner_organization_id = other.id
        session.commit()
        with pytest.raises(DomainError) as error:
            describe(session, service.organization_id, "answer", record_id)
        assert error.value.status == 404
    assert client.get("/api/monitoring-context", params={"kind": "answer", "id": record_id}).status_code == 404
