"""Jurisdiction and instrument context alone do not establish a shared subject."""

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from test_relation_profile_freshness import analyse
from test_topic_matching import add_event, create_topic

from helvetic_lens.models import (
    OrganizationRelationCandidate,
    RegulatoryEvent,
    RegulatoryWork,
    RelationCandidate,
    RelationImpactAnalysis,
    TopicEventMatch,
)
from helvetic_lens.relation_candidates import RULE_REVISION, score_candidate, score_pair
from helvetic_lens.topic_matching import generate_for_events

OPTIONS = {"source_authority": "basel_stadt", "target_authority": "basel_stadt",
           "source_kind": "act", "target_kind": "act"}


@pytest.mark.parametrize("source,target", [
    ("Reglement für die Benützung des Naturbads der Gemeinde Riehen", "Asylvertrag Riehen Bettingen"),
    ("Benützungs- und Gebührenreglement Baslerhofscheune Bettingen", "Asylvertrag Riehen Bettingen"),
    ("Zonenordnung Riehen", "Asylvertrag Riehen"),
    ("Interkantonale Vereinbarung über den schweizerischen Hochschulbereich", "Interkantonale Vereinbarung öffentliches Beschaffungswesen"),
    ("Interkantonale Vereinbarung über Beiträge an die Bildungsgänge", "Interkantonale Vereinbarung öffentliches Beschaffungswesen"),
    ("Verordnung über den Verkehr im Kanton Bern", "Verordnung über Integration im Kanton Bern"),
    ("Convention intercantonale sur les transports à Berne", "Convention intercantonale sur la migration à Berne"),
    ("Accordo intercantonale sui trasporti a Berna", "Accordo intercantonale sulla migrazione a Berna"),
    ("Cunvegna davart il traffic en il cantun", "Cunvegna davart la migraziun en il cantun"),
    ("Basel municipal transport agreement", "Basel municipal migration agreement"),
])
def test_geographic_or_agreement_overlap_alone_is_not_a_relation(source, target):
    assert score_candidate(source, target, **OPTIONS) is None
    assert score_candidate(source, target, shared_norms=1, **OPTIONS) is not None


@pytest.mark.parametrize("source,target,subject", [
    ("Integration in Riehen", "Integration in Basel", "integration"),
    ("Migration im Kanton Bern", "Migration und Integration in Bern", "migration"),
    ("Interkantonale Vereinbarung öffentliches Beschaffungswesen", "Beschaffungswesen Basel", "beschaffungswesen"),
    ("Convention intercantonale sur la migration", "Migration à Berne", "migration"),
    ("Accordo intercantonale sulla migrazione", "Migrazione a Berna", "migrazione"),
    ("Cunvegna davart la migraziun", "Migraziun en il cantun", "migraziun"),
    ("Basel migration agreement", "Bern migration regulation", "migration"),
])
def test_substantive_subject_still_matches_within_or_across_pilot_geography(source, target, subject):
    score = score_candidate(source, target, **OPTIONS)
    assert score is not None
    title_reason = next(reason for reason in score.why if reason.startswith("Shared normalized"))
    assert subject in title_reason and "riehen" not in title_reason and "agreement" not in title_reason


def test_confirmed_official_relation_does_not_depend_on_title_geography():
    source = SimpleNamespace(id="source", title="Basel traffic agreement")
    target = SimpleNamespace(id="target", title="Basel migration agreement")
    official = SimpleNamespace(state="confirmed", subject_work_id="source", object_work_id="target",
                               relation_type="amends", provenance_method="official_metadata")
    assert score_pair(source, None, target, official).components == {"confirmed_relation": 1.0}


def test_geographic_topic_matching_keeps_its_independent_vocabulary(harness):
    client, _, service, _ = harness
    topic = create_topic(client, concepts=["Riehen public policy"], synonyms=[], exclusions=[])
    event_id = add_event(service, title="Reglement für die Benützung des Naturbads in Riehen")
    with service.db.session(include_all_organizations=True) as session:
        result = generate_for_events(session, [session.get(RegulatoryEvent, event_id)], service.settings)
        assert result["matched"] == 1
        match = session.scalar(select(TopicEventMatch).where(TopicEventMatch.topic_id == topic["id"]))
        assert any(signal.get("type") == "fts_term" and "riehen" in signal["tokens"] for signal in match.reason_signals_json)


def test_reprocess_previews_and_rejects_geographic_noise_with_intact_history(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        source = session.get(RegulatoryWork, candidate.source_work_id)
        target = session.get(RegulatoryWork, candidate.target_work_id)
        source.title, target.title = "Reglement Naturbad Riehen", "Asylvertrag Riehen"
        source.metadata_json, target.metadata_json = {}, {}
        session.get(RegulatoryEvent, candidate.event_id).evidence_json = {}
        candidate.rule_revision = "relation-candidate-v3"
        original_deliveries = session.scalar(select(func.count()).select_from(OrganizationRelationCandidate))
        session.commit()
    for dry_run in (True, False):
        job = service.enqueue_relation_reprocessing(
            "26ebba44-f42f-47bf-a372-0c222e36cf31" if dry_run else "69e6b35c-cf10-40b0-b2e5-2b501fcff4d3",
            dry_run=dry_run,
        )
        result = asyncio.run(service.execute_job(job["id"]))["result"]["data"]
        assert result["rejected"] == 1 and result["ai_calls"] == 0
        with service.db.session() as session:
            candidate = session.get(RelationCandidate, saved["candidate_id"])
            assert candidate.rule_revision == ("relation-candidate-v3" if dry_run else RULE_REVISION)
            assert candidate.status == ("active" if dry_run else "rejected")
            assert session.scalar(select(func.count()).select_from(OrganizationRelationCandidate)) == original_deliveries
            assert session.get(RelationImpactAnalysis, saved["id"]).result == saved["result"]
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["status"] == "no_supported_impact" and item["severity"] == "unknown"
    assert "not a legal no-impact judgment" in item["potential_effect"]
    assert len(model.calls) == 1
