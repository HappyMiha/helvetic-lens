"""One private-topic policy for native readers, feeds and existing jobs.

HTTP queries receive the policy centrally, including alternate native routes and
scalar/count projections. Workers keep their native organization-scoped execution;
recipient projections use the same predicate explicitly. Shared brief admission
excludes private topics because its materialized conclusions are workspace-wide.
"""
from copy import deepcopy

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import with_loader_criteria

from .models import (
    DigestDelivery,
    Job,
    MonitoringTopic,
    MonitoringTopicRevision,
    TopicEventMatch,
    TopicMatchReview,
)
from .product_models import DossierMember


def visible(user_id, model=MonitoringTopic):
    members = DossierMember.__table__
    return or_(model.dossier_id.is_(None), model.dossier_id.in_(
        select(members.c.dossier_id).where(members.c.user_id == user_id)))


def topic_ids(user_id):
    topic = MonitoringTopic.__table__
    return select(topic.c.id).where(visible(user_id, topic.c))


def request_policy(statement):
    from .product_access import _request

    context = _request.get()
    if context is None:
        return statement
    user_id = context[2].user_id if context[2] else None
    ids = topic_ids(user_id)
    match = TopicEventMatch.__table__
    matches = select(match.c.id).where(match.c.topic_id.in_(ids))
    deliveries = DigestDelivery.__table__
    own_deliveries = select(deliveries.c.id).where(deliveries.c.user_id == user_id)
    members = DossierMember.__table__
    member_dossiers = select(members.c.dossier_id).where(members.c.user_id == user_id)
    return statement.options(
        with_loader_criteria(MonitoringTopic, lambda cls: or_(cls.dossier_id.is_(None), cls.dossier_id.in_(member_dossiers)), include_aliases=True),
        with_loader_criteria(MonitoringTopicRevision, lambda cls: cls.topic_id.in_(ids), include_aliases=True),
        with_loader_criteria(TopicEventMatch, lambda cls: cls.topic_id.in_(ids), include_aliases=True),
        with_loader_criteria(TopicMatchReview, lambda cls: cls.match_id.in_(matches), include_aliases=True),
        with_loader_criteria(Job, lambda cls: and_(or_(cls.target_type != "monitoring_topic", cls.target_id.in_(ids)),
            or_(cls.target_type != "digest_delivery", cls.target_id.in_(own_deliveries))), include_aliases=True),
    )


def guard_job_write(session, job_id):
    from .product_access import current_user_id, require_topic

    user_id = current_user_id()
    if not user_id:
        return
    job = session.get(Job, job_id)
    if job and job.target_type == "monitoring_topic":
        require_topic(session, job.target_id, user_id)


def retained_delivery(session, delivery):
    """Historical mail is retained, but a new web read never restores revoked access."""
    from .digests import serialize_delivery

    result = serialize_delivery(delivery)
    summary = deepcopy(result["summary"])
    if not isinstance(summary.get("events"), list):
        return result
    ids = {topic["topic_id"] for event in summary["events"] for topic in event.get("topics", [])}
    allowed = set(session.scalars(select(MonitoringTopic.id).where(
        MonitoringTopic.id.in_(ids), visible(delivery.user_id)))) if ids else set()
    retained = []
    for event in summary["events"]:
        original = event.get("topics", [])
        event["topics"] = [topic for topic in original if topic["topic_id"] in allowed]
        changed = len(event["topics"]) != len(original)
        if changed:
            event["topics_truncated"] = False
            event.pop("brief", None)
        if not changed or event["topics"] or event.get("impacts") or event.get("monitored_documents"):
            retained.append(event)
    summary["events"] = retained
    result.update(summary=summary, item_count=len(retained))
    return result


def shared_matching_job(result):
    """An event-wide worker cursor/count spans private topics; expose job state only."""
    from .product_access import _request

    if _request.get() is None:
        return result  # Durable workers retain full checkpoint and progress data.
    result["progress"] = {"current": int(result["state"] == "succeeded"), "total": 1, "unit": "job"}
    if result["result"] is not None:
        data = result["result"]["data"] or {}
        result["result"]["data"] = {"status": data.get("status"), "details_redacted": True}
    for step in result["steps"]:
        step["progress"] = {"current": int(step["state"] == "succeeded"), "total": 1, "unit": "step"}
        step["details"] = {}
    return result
