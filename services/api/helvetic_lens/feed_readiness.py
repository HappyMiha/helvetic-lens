"""Bounded saved operational context for an empty feed; never a coverage verdict."""

from datetime import UTC, datetime

from sqlalchemy import select

from .corpus_access import visible
from .models import DocumentWatch, Job, Law, MonitoringTopic, MonitoringTopicRevision, SourcePackSubscription
from .topic_coverage import snapshot
from .topic_matching import EVALUATION_REVISION, HISTORY_REVISION, RULE_REVISION

LIMIT = 20


def _time(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def read(session, organization_id, *, now):
    topic, job = MonitoringTopic, Job
    rows = list(
        session.execute(
            select(topic.id, topic.current_revision, topic.created_at, MonitoringTopicRevision.name)
            .join(
                MonitoringTopicRevision,
                (MonitoringTopicRevision.topic_id == topic.id)
                & (MonitoringTopicRevision.revision == topic.current_revision)
                & (MonitoringTopicRevision.organization_id == organization_id),
            )
            .where(topic.organization_id == organization_id, topic.status == "active")
            .order_by(topic.created_at.desc(), topic.id.desc())
            .limit(LIMIT + 1)
        )
    )
    topics, more_topics = rows[:LIMIT], len(rows) > LIMIT
    latest = (
        select(job.id)
        .where(
            job.organization_id == organization_id,
            job.type == "topic_match_backfill",
            job.target_id == topic.id,
            job.payload["revision"].as_integer() == topic.current_revision,
        )
        .order_by(job.created_at.desc(), job.id.desc())
        .limit(1)
        .correlate(topic)
        .scalar_subquery()
    )
    jobs = (
        {
            row.topic_id: row
            for row in session.execute(
                select(
                    topic.id.label("topic_id"),
                    job.state,
                    job.idempotency_key,
                    job.result_json["status"].as_string().label("result_status"),
                    job.result_json["has_more"].as_boolean().label("has_more"),
                    job.payload["checkpoint"]["captured_at"].as_string().label("captured"),
                    job.payload["checkpoint"]["cursor"]["created_at"].as_string().label("through"),
                    job.payload["checkpoint"]["processed"].as_integer().label("processed"),
                    job.payload["checkpoint"]["remaining"].as_integer().label("remaining"),
                )
                .select_from(topic)
                .join(job, job.id == latest)
                .where(topic.organization_id == organization_id, topic.id.in_([row.id for row in topics]))
            )
        }
        if topics
        else {}
    )
    items = []
    for row in topics:
        recorded = jobs.get(row.id)
        expected = f"{HISTORY_REVISION}:{RULE_REVISION}:{EVALUATION_REVISION}:{row.id}:{row.current_revision}"
        current = recorded is not None and recorded.idempotency_key == expected
        status = "not_started"
        if recorded:
            status = recorded.state
            if not current:
                status = "superseded"
            elif status == "succeeded":
                status = (
                    "complete"
                    if recorded.result_status == "complete"
                    and not recorded.has_more
                    and recorded.remaining == 0
                    else "unverified"
                )
        items.append(
            {
                "id": row.id,
                "name": row.name,
                "url": f"/topics#topic-{row.id}",
                "monitoring_from": _time(row.created_at),
                "history_status": status,
                "captured_at": _time(recorded.captured) if recorded and current else None,
                "processed_through": _time(recorded.through) if recorded and current else None,
                "processed": recorded.processed if recorded and current else None,
                "remaining": recorded.remaining if recorded and current else None,
            }
        )
    packs = list(
        session.scalars(
            select(SourcePackSubscription.pack_id)
            .where(
                SourcePackSubscription.organization_id == organization_id,
                SourcePackSubscription.enabled.is_(True),
            )
            .order_by(SourcePackSubscription.pack_id)
            .limit(LIMIT + 1)
        )
    )
    coverage = snapshot(session, packs[:LIMIT], now=now, organization_id=organization_id)
    streams = {
        (stream["connector"], stream["stream"]): stream
        for pack in coverage["items"]
        for stream in pack["streams"]
    }
    pending = any(pack["subscription_state"] in {"queued", "backfilling"} for pack in coverage["items"]) or any(
        stream["last_run_status"] in {"queued", "running"} for stream in streams.values()
    )
    attention = (
        len(coverage["items"]) < min(len(packs), LIMIT)
        or any(pack["unknown_stream_count"] for pack in coverage["items"])
        or any(pack["subscription_state"] in {"failed", "partial"} for pack in coverage["items"])
        or any(
            not stream["enabled"]
            or stream["last_reported_health"] in {"degraded", "failed", "error", "unavailable"}
            or stream["last_run_status"] in {"failed", "partial"}
            or stream["next_attempt_past_due"]
            for stream in streams.values()
        )
    )
    watch = bool(
        session.scalar(
            select(DocumentWatch.id)
            .join(Law, Law.id == DocumentWatch.law_id)
            .where(
                DocumentWatch.organization_id == organization_id,
                DocumentWatch.active.is_(True),
                visible(Law, organization_id),
            )
            .limit(1)
        )
    )
    return {
        "captured_at": _time(now),
        "scope": "bounded_saved_organization_state",
        "ai_calls": 0,
        "active_document_watch": watch,
        "topics": items,
        "more_topics": more_topics,
        "enabled_pack_count_shown": min(len(packs), LIMIT),
        "more_packs": len(packs) > LIMIT,
        "sources_pending": pending,
        "sources_need_attention": attention,
        "source_freshness_verified": False,
        "quiet_period_verified": False,
    }
