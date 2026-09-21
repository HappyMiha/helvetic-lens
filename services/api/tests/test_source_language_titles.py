"""A shared multilingual work must not relabel its exact language evidence."""

import pytest
from sqlalchemy import select
from test_interest_admission import model_identity, setup
from test_relation_analysis import relation_delivery
from test_topic_validity import evaluate

from helvetic_lens.corpus_access import event_expression_labels
from helvetic_lens.interest_admission import current_key
from helvetic_lens.models import RegulatoryEvent, RegulatoryExpression, RegulatoryWork, RelationCandidate
from helvetic_lens.relation_candidates import score_candidate


@pytest.mark.parametrize("expression_title", ["Selected English retention title", "  "])
def test_feed_evidence_comparison_and_brief_share_exact_source_title(harness, expression_title):
    client, _, _, model = harness
    service, event_id, version_id, topics = setup(harness)
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        work = session.get(RegulatoryWork, event.work_id)
        work.title = "Titolo italiano retention"
        session.get(RegulatoryExpression, event.expression_id).title = expression_title
        session.commit()
    evaluate(service, topics[0], event_id, "history")
    expected = expression_title.strip() or "Titolo italiano retention"
    card = next(row for row in client.get("/api/interest-feed").json()["items"] if row["event_id"] == event_id)
    assert card["title"] == expected and card["document_language"] == "en"
    for url in (f"/api/regulatory-versions/{version_id}", f"/api/regulatory-versions/{version_id}/page",
                f"/api/registry/events/{event_id}/comparison"):
        response = client.get(url)
        assert response.status_code == 200, response.text
        assert response.json()["law_name" if url.endswith("/page") else "title"] == expected
    with service.db.session() as session:
        dossier, _ = current_key(session, service.organization_id, event_id, model=model_identity())
        assert dossier.event.title == expected
        assert session.get(RegulatoryWork, event.work_id).title == "Titolo italiano retention"
    assert not model.calls


def test_inbox_uses_expression_title_and_rejects_foreign_work_labels(harness):
    client, _, service, _ = harness
    relation_delivery(harness)
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, session.scalar(select(RelationCandidate.event_id)))
        expression = session.get(RegulatoryExpression, event.expression_id)
        expression.title = "Selected English retention proposal"
        session.get(RegulatoryWork, event.work_id).title = "Titolo italiano retention"
        session.commit()
        event_id = event.id
    rows = client.get("/api/impact-inbox").json()["items"]
    assert next(row for row in rows if row["event_id"] == event_id)["title"] == "Selected English retention proposal"
    with service.db.session() as session:
        other = RegulatoryWork(kind="act", authority="synthetic", canonical_key="foreign-title-test",
                               title="Foreign work")
        session.add(other)
        session.flush()
        foreign = RegulatoryExpression(work_id=other.id, language="de", expression_key="foreign-title",
                                       title="This unrelated title must not be disclosed")
        session.add(foreign)
        session.flush()
        session.get(RegulatoryEvent, event_id).expression_id = foreign.id
        session.flush()
        assert event_expression_labels(session, service.organization_id, [event_id]) == {}
        with pytest.raises(ValueError):
            event_expression_labels(session, service.organization_id, [str(n) for n in range(101)])


@pytest.mark.parametrize("source, expected", [
    ("Risultato dell'emissione dei prestiti federali", False),
    ("Listini dei corsi (ICTax)", False),
    ("Nuove misure per la protezione dei dati", True),
])
def test_italian_function_words_do_not_invent_related_laws(source, expected):
    options = dict(source_authority="swiss_confederation", target_authority="swiss_confederation",
                   source_kind="official_notice", target_kind="act")
    score = score_candidate(source, "Legge federale sulla protezione dei dati", **options)
    assert (score is not None) is expected
    assert score_candidate(source, "Legge federale sulla protezione dei dati", shared_norms=1, **options) is not None
