"""Digest projection over the same current interests as Today, without inference."""
from datetime import UTC, datetime

from sqlalchemy import or_, select

from .impact_inbox import ImpactInboxFilters, _iso
from .interest_feed import InterestFeedReader
from .models import RegulatoryEvent, RegulatoryEventUserState

PROJECTION_VERSION = "digest-interests-v2"


class DigestReader(InterestFeedReader):
    def _digest_events(self, filters, captured):
        # This internal reader accepts only the delivery contract, not the richer
        # inbox filters. Never silently ignore an added filter at a future call site.
        if any((filters.source, filters.severity, filters.item_type, filters.watched_law,
                filters.state, filters.candidate)):
            raise ValueError("Unsupported digest selection filter")
        query = self._events(captured)
        if filters.detected_from is not None:
            query = query.where(RegulatoryEvent.detected_at >= filters.detected_from)
        if filters.detected_before is not None:
            query = query.where(RegulatoryEvent.detected_at < filters.detected_before)
        if filters.event_ids is not None:
            query = query.where(RegulatoryEvent.id.in_(filters.event_ids))
        if filters.sources:
            query = query.where(or_(RegulatoryEvent.connector.in_(filters.sources),
                                    RegulatoryEvent.authority.in_(filters.sources)))
        if filters.excluded_states:
            excluded = select(RegulatoryEventUserState.id).where(
                RegulatoryEventUserState.organization_id == self.organization_id,
                RegulatoryEventUserState.principal_key == self.principal,
                RegulatoryEventUserState.event_id == RegulatoryEvent.id,
                RegulatoryEventUserState.state.in_(filters.excluded_states)).exists()
            query = query.where(~excluded)
        return query

    def source_options(self, session):
        rows = session.execute(self._digest_events(ImpactInboxFilters(), datetime.now(UTC))
            .with_only_columns(RegulatoryEvent.connector, RegulatoryEvent.authority).distinct())
        return sorted({value for row in rows for value in row if value})

    def event_page(self, session, filters, *, cursor=None, page_size=50):
        if not 1 <= page_size <= 50:
            raise ValueError("Choose an event page size between 1 and 50.")
        captured = filters.admitted_before or datetime.now(UTC)
        query = self._digest_events(filters, captured)
        if cursor:
            stamp = datetime.fromisoformat(cursor["detected_at"])
            query = query.where(or_(RegulatoryEvent.detected_at < stamp,
                (RegulatoryEvent.detected_at == stamp) & (RegulatoryEvent.id < cursor["id"])))
        keys = list(session.execute(query.with_only_columns(RegulatoryEvent.id, RegulatoryEvent.detected_at)
            .order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc()).limit(page_size + 1)))
        selected = keys[:page_size]
        events = list(session.scalars(select(RegulatoryEvent).where(
            RegulatoryEvent.id.in_([row.id for row in selected]))
            .order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc()))) if selected else []
        cards = self._cards(session, events, captured)
        return {"items": [{**card, "items": card["law_impacts"]} for card in cards],
                "scanned": len(selected), "has_more": len(keys) > page_size,
                "admitted_before": _iso(captured),
                "cursor": {"detected_at": _iso(selected[-1].detected_at), "id": selected[-1].id}
                    if selected else cursor}
