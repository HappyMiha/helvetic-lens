"""Append-only semantic judgements, independent of immutable publisher versions."""
from copy import deepcopy

from sqlalchemy import exists, select

from .feed_models import FeedAssessment, FeedUpdate
from .product_api import fail, iso
from .product_operations import fingerprint


def next_unassessed(session, feed, specification, after_sequence=0):
    decided = exists(select(FeedAssessment.id).where(FeedAssessment.update_id == FeedUpdate.id,
        FeedAssessment.spec_binding == specification["binding"], FeedAssessment.verdict != "unavailable"))
    return session.scalar(select(FeedUpdate).where(FeedUpdate.feed_id == feed.id,
        FeedUpdate.sequence > after_sequence, ~decided).order_by(FeedUpdate.sequence).limit(1))


def latest_assessment(session, feed, update, specification):
    if update.feed_id != feed.id:
        fail("Feed observation not found.", 404, "not_found")
    return session.scalar(select(FeedAssessment).where(FeedAssessment.update_id == update.id,
        FeedAssessment.spec_binding == specification["binding"])
        .order_by(FeedAssessment.created_at.desc(), FeedAssessment.id.desc()).limit(1))


def persist_assessment(session, feed, update, specification, plan, decision):
    from .feed_intelligence import cached, spec

    if (update.feed_id != feed.id or spec(session, feed)["binding"] != specification["binding"]
            or not cached(specification, plan) or decision.get("verdict") not in {"relevant", "uncertain", "unrelated", "unavailable"}):
        fail("The semantic feed context changed; this judgement was not saved.", 409, "feed_intelligence_changed")
    key = fingerprint(decision)
    existing = session.scalar(select(FeedAssessment).where(FeedAssessment.update_id == update.id,
        FeedAssessment.spec_binding == specification["binding"], FeedAssessment.decision_key == key))
    if existing:
        return existing
    row = FeedAssessment(organization_id=feed.organization_id, feed_id=feed.id, update_id=update.id,
        spec_binding=specification["binding"], plan_binding=fingerprint(plan), decision_key=key,
        verdict=decision["verdict"], decision_json=deepcopy(decision))
    session.add(row)
    session.flush()
    return row


def current_binding(session, feed):
    from .config import DomainError
    from .feed_intelligence import spec

    try:
        return spec(session, feed)["binding"]
    except DomainError:
        return None


def verdict_expression(binding):
    return select(FeedAssessment.verdict).where(FeedAssessment.update_id == FeedUpdate.id,
        FeedAssessment.spec_binding == binding).order_by(FeedAssessment.created_at.desc(), FeedAssessment.id.desc()).limit(1).scalar_subquery()


def projection(row):
    if not row:
        return {"verdict": "pending", "engine": None,
            "scope": "Semantic relevance has not been assessed for the current search settings."}
    saved = row.decision_json
    return {"id": row.id, "verdict": row.verdict, "assessed_at": iso(row.created_at),
        **{key: deepcopy(saved[key]) for key in ("engine", "model", "confidence", "selected_probability",
            "scope", "basis", "error", "reading_complete") if key in saved},
        "evaluated_characters": saved.get("assessed_characters", saved.get("evaluated_characters")),
        "total_characters": saved.get("original_characters", saved.get("total_characters")),
        "portions": len(saved["portions"]) if isinstance(saved.get("portions"), list) else saved.get("portions")}


def history_payload(session, feed, rows, binding):
    from .feed_intelligence import settings
    from .feed_operations import update_payload

    feedback = {value["update_id"]: value["verdict"] for value in settings(feed)["feedback"]}
    ids = [row.id for row in rows]
    assessments = {}
    if ids and binding:
        for row in session.scalars(select(FeedAssessment).where(FeedAssessment.update_id.in_(ids),
                FeedAssessment.spec_binding == binding).order_by(FeedAssessment.created_at, FeedAssessment.id)):
            assessments[row.update_id] = row
    return [{**update_payload(row), "relevance": projection(assessments.get(row.id)),
        "feedback": feedback.get(row.id)} for row in rows]
