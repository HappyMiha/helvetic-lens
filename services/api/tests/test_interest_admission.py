"""Current saved inputs, not a truncated feed card or caller-provided dossier."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from test_interest_assessment import Model, dossier, run
from test_relation_analysis import relation_delivery
from test_topic_matching import add_event, create_topic
from test_topic_validity import evaluate

from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.interest_admission import assemble, current_key
from helvetic_lens.interest_assessment import fingerprint, manifest
from helvetic_lens.interest_assessment_store import AssessmentStore
from helvetic_lens.models import (
    DocumentWatch,
    InterestEventAssessment,
    MonitoringTopic,
    MonitoringTopicRevision,
    Organization,
    OrganizationRelationCandidate,
    OrganizationRelationReview,
    Profile,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryWork,
    RelationCandidate,
    TopicEventMatch,
    Version,
)


def model_identity():
    return dossier().model


def draft_for(value):
    source_id = next(row.id for row in value.evidence if row.source_kind == "event")
    claim = {"text": "Synthetic saved document provides a review lead.", "evidence_ids": [source_id]}
    return {"what_happened": dict(claim),
            "why_in_radar": [{**claim, "interest_id": row.id} for row in value.interests],
            "importance": {**claim, "level": "low" if value.profile_facts else "undetermined",
                           "profile_fact_ids": [value.profile_facts[0].id] if value.profile_facts else []},
            "affected_area_ids": [], "next_step": {**claim, "kind": "no_action_now", "interest_id": None},
            "uncertainty": "Synthetic test fixture, not a legal conclusion."}


def source(service, event_id, count=2):
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        version = session.get(RegulatoryDocumentVersion, event.document_version_id) if event.document_version_id else None
        if version is None:
            version = RegulatoryDocumentVersion(expression_id=event.expression_id, version_key="complete-input-test")
            session.add(version)
            session.flush()
            event.document_version_id = version.id
        version.artifact_key = "a" * 64 + ".html"
        version.source_url = event.source_url
        version.passages = [{"id": f"article-{i}", "text": f"Synthetic naturalisation source clause {i}.", "position": i + 1}
                            for i in range(count)]
        version.text = "\n\n".join(row["text"] for row in version.passages)
        session.commit()
    return version.id


def setup(harness, topics=1, units=2):
    client, _, service, _ = harness
    event_id = add_event(service)
    version_id = source(service, event_id, units)
    values = []
    for index in range(topics):
        topic = create_topic(client, key=f"admission-test-{index}", name=f"Naturalisation interest {index}")
        evaluate(service, topic, event_id, "history")
        values.append(topic)
    return service, event_id, version_id, values


def read(service, event_id, **kwargs):
    with service.db.session() as session:
        return current_key(session, service.organization_id, event_id, model=model_identity(), **kwargs)


@pytest.mark.parametrize("locale", ["de", "fr", "it", "rm", "en"])
def test_all_interests_and_full_passages_not_feed_preview(harness, locale):
    service, event_id, version_id, topics = setup(harness, topics=7, units=12)
    value, key = read(service, event_id, locale=locale)
    assert len(value.interests) == 7 and len(value.evidence) == 12
    assert {row.revision for row in value.interests} == {t["plan"]["id"] for t in topics}
    assert all(len(item.evidence_ids) == 12 for item in value.interests)
    assert all(row.version_id == version_id for row in value.evidence)
    assert value.locale == locale and key == fingerprint(manifest(value))
    assert value.event.official_status is None and value.event.official_dates == []
    assert value.event.event_type == "amended"
    assert "not a before/after comparison" in value.event.limitations[0]
    assert harness[3].calls == []


@pytest.mark.parametrize("change", ["paused", "archived", "revision", "evidence", "expired", "rejected", "muted", "revoked", "private"])
def test_invalid_interest_is_not_admitted(harness, change):
    service, event_id, _, topics = setup(harness)
    with service.db.session(include_all_organizations=True) as session:
        topic = session.get(MonitoringTopic, topics[0]["id"])
        match = session.scalar(select(TopicEventMatch).where(TopicEventMatch.event_id == event_id))
        if change in {"paused", "archived"}:
            topic.status = change
        elif change == "revision":
            topic.current_revision += 1
        elif change == "evidence":
            session.get(RegulatoryEvent, event_id).evidence_json = {"new": "corrected"}
        elif change == "expired":
            match.expires_at = utcnow() - timedelta(seconds=1)
        elif change in {"rejected", "muted"}:
            match.decision_status = change
        elif change == "revoked":
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        elif change == "private":
            other = Organization(name="Foreign organization", slug="admission-foreign")
            session.add(other)
            session.flush()
            event = session.get(RegulatoryEvent, event_id)
            session.get(RegulatoryWork, event.work_id).owner_organization_id = other.id
        session.commit()
    with pytest.raises(DomainError) as error:
        read(service, event_id)
    assert error.value.code in {"not_found", "interest_not_current"}


@pytest.mark.parametrize("change", ["text", "artifact", "profile", "runtime", "locale"])
def test_fingerprint_changes_for_real_input_changes_and_not_reading_state(harness, change):
    service, event_id, version_id, _ = setup(harness)
    _, before = read(service, event_id)
    kwargs = {}
    with service.db.session() as session:
        version = session.get(RegulatoryDocumentVersion, version_id)
        if change == "text":
            version.passages = [{"id": "article-0", "text": "Corrected source evidence."}]
        elif change == "artifact":
            version.artifact_key = "b" * 64 + ".pdf"
        elif change == "profile":
            profile = session.scalar(select(Profile).where(Profile.organization_id == service.organization_id))
            profile.description = "A local bakery organization."
            # The content hash must catch old clients that forgot the revision.
        session.commit()
    if change == "locale":
        kwargs["locale"] = "fr"
    if change == "runtime":
        with service.db.session() as session:
            value = assemble(session, service.organization_id, event_id,
                             model=model_identity().model_copy(update={"runtime_fingerprint": "f" * 64}))
        after = fingerprint(manifest(value))
    else:
        _, after = read(service, event_id, **kwargs)
    assert before != after
    assert harness[3].calls == []


@pytest.mark.parametrize("change", ["missing_version", "missing_artifact", "no_passages", "duplicate_ids", "wrong_work", "wrong_expression", "oversized", "too_many_units"])
def test_missing_or_unbounded_evidence_never_becomes_partial_dossier(harness, change):
    service, event_id, version_id, _ = setup(harness)
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        version = session.get(RegulatoryDocumentVersion, version_id)
        if change == "missing_version":
            event.document_version_id = None
        elif change == "missing_artifact":
            version.artifact_key = None
        elif change == "no_passages":
            version.passages = []
        elif change == "duplicate_ids":
            version.passages = [version.passages[0], version.passages[0]]
        elif change in {"wrong_work", "wrong_expression"}:
            work = session.get(RegulatoryWork, event.work_id)
            if change == "wrong_work":
                work = RegulatoryWork(kind="act", authority="fedlex", canonical_key="wrong-input-work", title="Wrong source")
                session.add(work)
                session.flush()
            expression = RegulatoryExpression(work_id=work.id, language="fr", expression_key="wrong-input-expression")
            session.add(expression)
            session.flush()
            version.expression_id = expression.id
        elif change == "oversized":
            version.passages = [{"id": "article-0", "text": "x" * 16001}]
        elif change == "too_many_units":
            version.passages = [{"id": str(i), "text": "saved text"} for i in range(65)]
        session.commit()
    # Event metadata changes may also invalidate the saved match; either way no dossier.
    with pytest.raises(DomainError):
        read(service, event_id)
    assert harness[3].calls == []


def test_foreign_worker_cannot_assemble_even_with_privileged_session(harness):
    service, event_id, _, _ = setup(harness)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Other", slug="admission-other")
        session.add(other)
        session.flush()
        with pytest.raises(DomainError) as error:
            assemble(session, other.id, event_id, model=model_identity())
        assert error.value.status == 404


def test_prepare_generate_finish_reuses_exact_brief_and_rechecks_inputs(harness):
    service, event_id, _, topics = setup(harness, topics=2)
    store = AssessmentStore(service.organization_id)
    with service.db.session() as session:
        record, created, value = store.prepare_current(session, event_id, model=model_identity(), context_char_limit=40000)
        key, input_key = record.id, record.input_fingerprint
        token = store.claim(session, key, input_key)
        session.commit()
    assert created and token
    model = Model(draft_for(value))
    result, usage = run(model, value)
    assert result["input_limitations"] == value.event.limitations
    assert result["event_type"] == value.event.event_type
    with service.db.session() as session:
        assert store.finish_current(session, key, token, value, result, model=model_identity(), provider_calls=usage["provider_calls"])
        session.commit()
    with service.db.session() as session:
        saved, created, _ = store.prepare_current(session, event_id, model=model_identity(), context_char_limit=40000)
        assert saved.id == key and not created and saved.result == result
        assert store.exact(session, event_id, read(service, event_id)[1]).id == key
        session.commit()
    assert len(model.calls) == 1
    with service.db.session() as session:
        session.get(MonitoringTopic, topics[0]["id"]).status = "paused"
        session.commit()
    with service.db.session() as session:
        next_record, created, next_value = store.prepare_current(session, event_id, model=model_identity(), context_char_limit=40000)
        assert created and next_record.id != key and len(next_value.interests) == 1
        assert store.get(session, key).status == "succeeded"  # Immutable history.


@pytest.mark.parametrize("change", ["paused", "profile", "new_interest", "revoked", "runtime", "prompt"])
def test_changed_inputs_reject_fenced_inflight_completion(harness, change):
    service, event_id, _, topics = setup(harness)
    store = AssessmentStore(service.organization_id)
    with service.db.session() as session:
        record, _, value = store.prepare_current(session, event_id, model=model_identity(), context_char_limit=40000)
        key = record.id
        token = store.claim(session, key, record.input_fingerprint)
        session.commit()
    result, _ = run(Model(draft_for(value)), value)
    identity = model_identity()
    with service.db.session() as session:
        if change == "paused":
            session.get(MonitoringTopic, topics[0]["id"]).status = "paused"
        elif change == "profile":
            session.scalar(select(Profile).where(Profile.organization_id == service.organization_id)).description = "Changed profile"
        elif change == "revoked":
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        session.commit()
    if change == "new_interest":
        topic = create_topic(harness[0], key="late-admission-topic")
        evaluate(service, topic, event_id, "history")
    if change == "runtime":
        identity = identity.model_copy(update={"runtime_fingerprint": "f" * 64})
    with service.db.session() as session:
        options = {"instructions": "A newly approved instruction."} if change == "prompt" else {}
        assert not store.finish_current(session, key, token, value, result, model=identity, provider_calls=1, **options)
        assert store.get(session, key).status == "superseded"
        assert store.get(session, key).result is None
        session.commit()


def test_law_and_direct_watch_inputs_use_exact_legacy_evidence(harness):
    delivery_id, _ = relation_delivery(harness)
    service = harness[2]
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        event_id, target_id = candidate.event_id, candidate.target_work_id
        session.add(RegulatoryEventState(event_id=event_id))
        target = session.get(RegulatoryDocumentVersion, candidate.target_version_id)
        legacy_id = target.legacy_version_id
        session.commit()
    source(service, event_id)
    with service.db.session() as session:
        value = assemble(session, service.organization_id, event_id, model=model_identity())
        assert len(value.interests) == 1 and value.interests[0].kind == "law"
        assert any(row.version_id == legacy_id and row.source_kind == "monitored_law" for row in value.evidence)
        event = RegulatoryEvent(work_id=target_id, expression_id=target.expression_id,
            document_version_id=target.id, authority="fedlex", event_type="created",
            dedupe_key="direct-admission-event", detected_at=utcnow(), provenance_method="legacy_mapping")
        session.add(event)
        session.flush()
        session.add(RegulatoryEventState(event_id=event.id))
        session.commit()
        value = assemble(session, service.organization_id, event.id, model=model_identity())
        assert len(value.interests) == 1 and value.interests[0].kind == "direct_watch"
        assert all(row.version_id == legacy_id for row in value.evidence)


@pytest.mark.parametrize("change", ["paused", "dismissed", "expired", "old_rules", "rejected", "foreign_legacy", "new_target", "withdrawn_signals"])
def test_law_admission_excludes_inactive_or_foreign_evidence(harness, change):
    delivery_id, _ = relation_delivery(harness)
    service = harness[2]
    with service.db.session(include_all_organizations=True) as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        event_id = candidate.event_id
        session.add(RegulatoryEventState(event_id=event_id))
        if change == "paused":
            session.get(DocumentWatch, delivery.watch_id).active = False
        elif change == "dismissed":
            delivery.status = "dismissed"
        elif change == "expired":
            candidate.expires_at = utcnow() - timedelta(seconds=1)
        elif change == "old_rules":
            candidate.rule_revision = "old-rules"
        elif change == "rejected":
            session.add(OrganizationRelationReview(organization_candidate_id=delivery.id, decision="rejected"))
        elif change == "foreign_legacy":
            target = session.get(RegulatoryDocumentVersion, candidate.target_version_id)
            other = Organization(name="Private owner", slug="foreign-legacy-admission")
            session.add(other)
            session.flush()
            session.get(Version, target.legacy_version_id).owner_organization_id = other.id
        elif change == "new_target":
            target = session.get(RegulatoryDocumentVersion, candidate.target_version_id)
            session.add(RegulatoryDocumentVersion(expression_id=target.expression_id,
                version_key="new-law-wording", created_at=utcnow() + timedelta(seconds=1)))
        elif change == "withdrawn_signals":
            source_work = session.get(RegulatoryWork, candidate.source_work_id)
            source_work.title, source_work.metadata_json = "Railway bridge dimensions", {}
            session.get(RegulatoryEvent, event_id).evidence_json = {}
        session.commit()
    source(service, event_id)
    with pytest.raises(DomainError):
        read(service, event_id)


def test_65_current_interests_fail_as_a_whole_not_a_sample(harness):
    service, event_id, _, _ = setup(harness, topics=65)
    with pytest.raises(DomainError) as error:
        read(service, event_id)
    assert error.value.code == "interest_context_exceeded"
    assert harness[3].calls == []


def test_full_traversal_continues_beyond_100_stale_candidates(harness):
    service, event_id, _, topics = setup(harness)
    with service.db.session() as session:
        template = session.scalar(select(TopicEventMatch).where(TopicEventMatch.event_id == event_id))
        revision = session.get(MonitoringTopicRevision, template.topic_revision_id)
        # All stale IDs sort before the actual current match, crossing a real
        # 100-record SQL page. These rows obey the same FK/unique constraints.
        for index in range(105):
            topic = MonitoringTopic(id=str(uuid4()), idempotency_key=f"stale-input-{index}", status="paused")
            session.add(topic)
            session.flush()
            copied = {column.name: getattr(revision, column.name) for column in revision.__table__.columns
                      if column.name not in {"id", "topic_id"}}
            old_revision = MonitoringTopicRevision(id=str(uuid4()), topic_id=topic.id, **copied)
            session.add(old_revision)
            session.flush()
            copied = {column.name: getattr(template, column.name) for column in template.__table__.columns
                      if column.name not in {"id", "topic_id", "topic_revision_id"}}
            session.add(TopicEventMatch(id=f"00000000-0000-0000-0000-{index:012d}",
                topic_id=topic.id, topic_revision_id=old_revision.id, **copied))
        session.commit()
    value, _ = read(service, event_id)
    assert len(value.interests) == 1 and value.interests[0].revision == topics[0]["plan"]["id"]


def test_reused_session_reloads_external_edits_and_excludes_other_profiles(harness):
    service, event_id, _, _ = setup(harness)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Foreign", slug="profile-admission-other")
        session.add(other)
        session.flush()
        session.add(Profile(id="other-private-profile", organization_id=other.id,
                            description="PRIVATE PROFILE MUST NOT APPEAR", business_areas=[]))
        session.commit()
    with service.db.session() as session:
        first = assemble(session, service.organization_id, event_id, model=model_identity())
        with service.db.session() as updater:
            profile = updater.scalar(select(Profile).where(Profile.organization_id == service.organization_id))
            profile.description = "New description from another transaction"
            updater.commit()
        second = assemble(session, service.organization_id, event_id, model=model_identity())
        assert fingerprint(manifest(first)) != fingerprint(manifest(second))
        assert "New description from another transaction" in second.model_dump_json()
        assert "PRIVATE PROFILE MUST NOT APPEAR" not in second.model_dump_json()


@pytest.mark.parametrize("blocked", ["characters", "cloud"])
def test_admission_budget_or_unapproved_cloud_does_not_persist_queued_work(harness, blocked):
    service, event_id, _, _ = setup(harness)
    model = model_identity()
    if blocked == "cloud":
        model = model.model_copy(update={"route": "cloud", "cloud_fallback_approved": False})
    with service.db.session() as session:
        with pytest.raises(DomainError) as error:
            AssessmentStore(service.organization_id).prepare_current(session, event_id, model=model,
                context_char_limit=100 if blocked == "characters" else 40000)
        assert error.value.code == ("cloud_not_approved" if blocked == "cloud" else "interest_context_exceeded")
        assert session.scalar(select(func.count()).select_from(InterestEventAssessment)) == 0
    assert harness[3].calls == []


def test_missing_profile_does_not_invent_organization_relevance(harness):
    service, event_id, _, _ = setup(harness)
    with service.db.session() as session:
        profile = session.scalar(select(Profile).where(Profile.organization_id == service.organization_id))
        profile.description, profile.business_areas = "", []
        session.commit()
    value, _ = read(service, event_id)
    assert value.profile_facts == []
    result, _ = run(Model(draft_for(value)), value)
    assert result["importance"]["level"] == "undetermined"
