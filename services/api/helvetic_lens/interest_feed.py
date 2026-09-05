"""One saved event per card, across watched laws and current topic matches.

A read projection only: no model calls, copied evidence, or second read history.
Candidate event pages are bounded; a stale topic candidate may leave a sparse page.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import DomainError
from .corpus_access import event_evidence_links
from .impact_inbox import ImpactInboxFilters, ImpactInboxReader, _iso
from .inbox_context import visible
from .models import (
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    MonitoringTopic,
    MonitoringTopicRevision,
    OrganizationRelationCandidate,
    RegulatoryDate,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryEventUserState,
    RegulatoryExpression,
    RegulatoryWork,
    RelationCandidate,
    TopicEventMatch,
)
from .topic_matching import describe_matches


def _jurisdictions(work, event):
    # Only recorded values; an unknown jurisdiction must not silently become CH.
    metadata = work.metadata_json if isinstance(work.metadata_json, dict) else {}
    evidence = event.evidence_json if isinstance(event.evidence_json, dict) else {}
    value = metadata.get("jurisdiction") or metadata.get("jurisdictions") or evidence.get("jurisdiction")
    values = value if isinstance(value, list) else [value]
    return sorted({item.strip() for item in values if isinstance(item, str) and item.strip()})


class InterestFeedReader(ImpactInboxReader):
    def _topics(self, captured: datetime):
        return (select(TopicEventMatch)
            .join(MonitoringTopic, MonitoringTopic.id == TopicEventMatch.topic_id)
            .join(MonitoringTopicRevision, MonitoringTopicRevision.id == TopicEventMatch.topic_revision_id)
            .join(RegulatoryEventState, (RegulatoryEventState.event_id == TopicEventMatch.event_id)
                  & (RegulatoryEventState.organization_id == self.organization_id))
            .where(TopicEventMatch.organization_id == self.organization_id,
                   MonitoringTopic.organization_id == self.organization_id,
                   MonitoringTopicRevision.organization_id == self.organization_id,
                   MonitoringTopicRevision.topic_id == MonitoringTopic.id,
                   MonitoringTopic.status == "active",
                   MonitoringTopicRevision.revision == MonitoringTopic.current_revision,
                   TopicEventMatch.match_status == "matching",
                   TopicEventMatch.matched_at < captured,
                   RegulatoryEventState.created_at < captured,
                   or_(TopicEventMatch.expires_at.is_(None), TopicEventMatch.expires_at > datetime.now(UTC))))

    def _watches(self, captured: datetime):
        return (select(LegacyDocumentMapping.work_id, DocumentWatch.id, DocumentWatch.law_id, DocumentWatch.display_name)
            .join(DocumentWatch, DocumentWatch.law_id == LegacyDocumentMapping.law_id)
            .join(Law, Law.id == DocumentWatch.law_id)
            .where(DocumentWatch.organization_id == self.organization_id, DocumentWatch.active.is_(True),
                   DocumentWatch.created_at < captured, LegacyDocumentMapping.created_at < captured,
                   visible(Law, self.organization_id), visible(LegacyDocumentMapping, self.organization_id)))

    def _events(self, captured: datetime):
        topics = self._topics(captured).with_only_columns(TopicEventMatch.event_id)
        laws = (select(RelationCandidate.event_id)
            .join(OrganizationRelationCandidate, OrganizationRelationCandidate.candidate_id == RelationCandidate.id)
            .where(OrganizationRelationCandidate.organization_id == self.organization_id,
                   OrganizationRelationCandidate.created_at < captured))
        return select(RegulatoryEvent).join(RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id).where(
            visible(RegulatoryWork, self.organization_id),
            or_(RegulatoryEvent.id.in_(topics), RegulatoryEvent.id.in_(laws),
                RegulatoryEvent.work_id.in_(self._watches(captured).with_only_columns(LegacyDocumentMapping.work_id))),
            RegulatoryEvent.detected_at <= captured)

    def _cards(self, session: Session, events: list[RegulatoryEvent], captured: datetime) -> list[dict]:
        if not events:
            return []
        ids = tuple(item.id for item in events)
        laws = {item["event_id"]: item for item in self.page(session, ImpactInboxFilters(
            event_ids=ids, admitted_before=captured))["items"]}
        records = list(session.scalars(self._topics(captured).where(TopicEventMatch.event_id.in_(ids))))
        matches = [match for start in range(0, len(records), 100)
                   for match in describe_matches(session, records[start:start + 100])]
        names = dict(session.execute(select(MonitoringTopicRevision.id, MonitoringTopicRevision.name).where(
            MonitoringTopicRevision.id.in_(self._topics(captured).where(TopicEventMatch.event_id.in_(ids))
                                         .with_only_columns(TopicEventMatch.topic_revision_id)))).all())
        topics: dict[str, list] = {}
        for match in matches:
            if not match["is_current"] or (match["decision_is_current"] and match["decision"] in {"rejected", "muted"}):
                continue
            topics.setdefault(match["event_id"], []).append({
                **match, "name": names[match["topic_revision_id"]],
                "url": f"/topics#topic-{match['topic_id']}",
            })
        works = {item.id: item for item in session.scalars(select(RegulatoryWork).where(
            RegulatoryWork.id.in_({item.work_id for item in events}), visible(RegulatoryWork, self.organization_id)))}
        evidence_links = event_evidence_links(session, self.organization_id, ids)
        languages = dict(session.execute(select(RegulatoryEvent.id, RegulatoryExpression.language)
            .join(RegulatoryExpression, RegulatoryExpression.id == RegulatoryEvent.expression_id)
            .where(RegulatoryEvent.id.in_(ids), RegulatoryExpression.work_id == RegulatoryEvent.work_id)).all())
        states = dict(session.execute(select(RegulatoryEventUserState.event_id, RegulatoryEventUserState.state).where(
            RegulatoryEventUserState.organization_id == self.organization_id,
            RegulatoryEventUserState.principal_key == self.principal,
            RegulatoryEventUserState.event_id.in_(ids))).all())
        # Event-specific dates only. A work publication date is not necessarily this development's date.
        dates: dict[str, list] = {}
        for fact in session.scalars(select(RegulatoryDate).where(
                RegulatoryDate.entity_type == "event", RegulatoryDate.entity_id.in_(ids),
                RegulatoryDate.kind.in_(["published_at", "decision_date", "effective_from", "effective_to"])
        ).order_by(RegulatoryDate.kind, RegulatoryDate.date_value, RegulatoryDate.id)):
            dates.setdefault(fact.entity_id, []).append({"kind": fact.kind, "value": fact.date_value,
                                                       "precision": fact.precision, "provenance": fact.provenance,
                                                       "source_url": fact.source_url})
        watches: dict[str, list] = {}
        for watch in session.execute(self._watches(captured).where(
                LegacyDocumentMapping.work_id.in_({event.work_id for event in events})).order_by(DocumentWatch.display_name, DocumentWatch.id)):
            watches.setdefault(watch.work_id, []).append({"watch_id": watch.id, "law_id": watch.law_id,
                                                         "name": watch.display_name, "url": f"/laws/{watch.law_id}"})
        result = []
        for event in events:
            work = works.get(event.work_id)
            law = laws.get(event.id)
            relevant = topics.get(event.id, [])
            if not work or (not law and not relevant and not watches.get(event.work_id)):
                continue
            result.append({
                "event_id": event.id, "event_url": f"/?event={event.id}", "title": work.title, "type": event.event_type,
                "jurisdictions": _jurisdictions(work, event),
                "document_language": languages.get(event.id),
                "provenance_method": event.provenance_method,
                "connector_health_at_detection": event.connector_health,
                "document_kind": work.kind, "lifecycle_status": work.lifecycle_status,
                "source": event.connector or event.authority, "authority": event.authority,
                "detected_at": _iso(event.detected_at), "official_dates": dates.get(event.id, []),
                "source_url": event.source_url or work.stable_official_url,
                "source_artifact_url": evidence_links.get(event.id),
                "read_state": states.get(event.id, "unread"),
                "severity": law["severity"] if law else "unknown",
                "law_impacts": law["items"] if law else [],
                "monitored_documents": watches.get(event.work_id, []),
                "topic_matches": sorted(relevant, key=lambda item: (item["name"], item["topic_id"])),
                "ai_coverage": law["coverage"] if law else {"analysed": 0, "total": 0},
            })
        return result

    def feed(self, session: Session, *, period: str = "all", state: str = "", cursor: str = "", limit: int = 20, event: str = "") -> dict:
        if period not in {"all", "today", "yesterday", "week", "month"} or state not in {"", "unread", "read", "dismissed", "muted"} or not 1 <= limit <= 50:
            raise DomainError("Choose a supported feed filter and page size.", 422, "invalid_feed_filter")
        if not isinstance(event, str) or len(event) > 36:
            raise DomainError("Choose a valid saved event.", 422, "invalid_feed_filter")
        scope = hashlib.sha256(json.dumps([self.organization_id, self.principal, period, state, event]).encode()).hexdigest()
        captured, after = datetime.now(UTC), None
        if cursor:
            try:
                if len(cursor) > 4096:
                    raise ValueError()
                data = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
                if data["v"] != 1 or data["scope"] != scope:
                    raise ValueError()
                captured = datetime.fromisoformat(data["captured"])
                position = datetime.fromisoformat(data["date"])
                if captured.tzinfo is None or position.tzinfo is None or not isinstance(data["id"], str) or not 1 <= len(data["id"]) <= 36:
                    raise ValueError()
                after = (position, data["id"])
            except (ValueError, KeyError, TypeError, UnicodeError, RecursionError) as exc:
                raise DomainError("Open the first feed page for these filters and account.", 422, "invalid_feed_cursor") from exc
        query = self._events(captured)
        if event:
            query = query.where(RegulatoryEvent.id == event)
        if period != "all":
            today = captured.astimezone(ZoneInfo("Europe/Zurich")).date()
            start = today - timedelta(days={"today": 0, "yesterday": 1, "week": 6, "month": 29}[period])
            end = today if period == "yesterday" else today + timedelta(days=1)
            query = query.where(RegulatoryEvent.detected_at >= datetime.combine(start, time.min, ZoneInfo("Europe/Zurich")).astimezone(UTC),
                                RegulatoryEvent.detected_at < datetime.combine(end, time.min, ZoneInfo("Europe/Zurich")).astimezone(UTC))
        if state:
            personal = select(RegulatoryEventUserState.id).where(
                RegulatoryEventUserState.organization_id == self.organization_id,
                RegulatoryEventUserState.principal_key == self.principal,
                RegulatoryEventUserState.event_id == RegulatoryEvent.id)
            query = query.where(~personal.where(RegulatoryEventUserState.state != "unread").exists() if state == "unread"
                                else personal.where(RegulatoryEventUserState.state == state).exists())
        if after:
            query = query.where(or_(RegulatoryEvent.detected_at < after[0],
                                    (RegulatoryEvent.detected_at == after[0]) & (RegulatoryEvent.id < after[1])))
        events = list(session.scalars(query.order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc()).limit(limit + 1)))
        more, events = len(events) > limit, events[:limit]
        next_cursor = None
        if more:
            payload = {"v": 1, "scope": scope, "captured": _iso(captured),
                       "date": _iso(events[-1].detected_at), "id": events[-1].id}
            next_cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return {"items": self._cards(session, events, captured), "scanned_event_count": len(events),
                "counts_scope": "page", "has_more": more, "next_cursor": next_cursor,
                "captured_at": _iso(captured), "period_timezone": "Europe/Zurich", "ai_calls": 0}

    def set_feed_state(self, session: Session, event_id: str, state: str) -> dict:
        if state not in {"unread", "read", "dismissed", "muted"}:
            raise DomainError("Choose a supported reading state.", 422, "invalid_inbox_state")
        captured = datetime.now(UTC)
        events = list(session.scalars(self._events(captured).where(RegulatoryEvent.id == event_id)))
        if not self._cards(session, events, captured):
            raise DomainError("This event is not in the organization's interest feed.", 404, "not_found")
        record = session.scalar(select(RegulatoryEventUserState).where(
            RegulatoryEventUserState.organization_id == self.organization_id,
            RegulatoryEventUserState.event_id == event_id, RegulatoryEventUserState.principal_key == self.principal))
        if record is None:
            record = RegulatoryEventUserState(organization_id=self.organization_id, event_id=event_id,
                                              user_id=self.user_id, principal_key=self.principal)
            session.add(record)
        record.state, record.updated_at = state, datetime.now(UTC)
        session.commit()
        return {"event_id": event_id, "state": state, "updated_at": _iso(record.updated_at)}
